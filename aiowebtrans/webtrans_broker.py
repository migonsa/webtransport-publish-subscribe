import argparse, asyncio, importlib, logging, time, sys, aioquic, signal
import aiosqlite as sql
from collections import deque
from email.utils import formatdate
from typing import Callable, Deque, Dict, List, Optional, Union

from aioquic.asyncio import QuicConnectionProtocol, serve
from aioquic.h0.connection import H0_ALPN, H0Connection
from aioquic.h3.connection import H3_ALPN, H3Connection
from aioquic.h3.events import (
    DatagramReceived,
    DataReceived,
    H3Event,
    HeadersReceived,
    WebTransportStreamDataReceived,
)
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import DatagramFrameReceived, ProtocolNegotiated, QuicEvent, ConnectionTerminated
from aioquic.quic.logger import QuicFileLogger
from aioquic.tls import SessionTicket

try:
    import uvloop
except ImportError:
    uvloop = None


AsgiApplication = Callable
HttpConnection = Union[H0Connection, H3Connection]

SERVER_NAME = "aioquic/" + aioquic.__version__



class SQLDatabase:
    def __init__(
        self,
        dbpath: str,
    ) -> None:
        self.dbpath = dbpath
        self.connection = None
        return

    async def connect(self) -> None:
        self.connection = await sql.connect(self.dbpath)
        assert isinstance(self.connection, sql.Connection)

    async def check_permissions(self, rol: str, user: str, password: str, topic: str) -> bool:
        result = False
        sql_query = "SELECT " + rol + " FROM perms INNER JOIN clients on perms.clientid=clients.id INNER JOIN topics on perms.topicid=topics.id WHERE clients.user=? AND clients.password=? AND topics.name=?"
        async with self.connection.execute_fetchall(sql_query, (user, password, topic)) as dbresult:
            if dbresult:
                result = bool(dbresult[0])
        return result
    
    async def get_topics(self) -> List[str]:
        result = []
        sql_query = "SELECT name from topics"
        async with self.connection.execute_fetchall(sql_query) as dbresult:
            if dbresult:
                result = [item[0] for item in dbresult]
        return result

    async def check_publisher(self, user: str, password: str, topic: str) -> bool:
        return await self.check_permissions('publish', user, password, topic)

    async def check_subscriber(self, user: str, password: str, topic: str) -> bool:
        return await self.check_permissions('subscribe', user, password, topic)
    
    async def close(self) -> None:
        if self.connection is not None:
            await self.connection.close()


class WebTransportHandler:
    def __init__(
        self,
        *,
        connection: HttpConnection,
        scope: Dict,
        stream_id: int,
        transmit: Callable[[], None],
        autoremove: Callable
    ) -> None:
        self.accepted = False
        self.closed = False
        self.connection = connection
        self.http_event_queue: Deque[DataReceived] = deque()
        self.queue: asyncio.Queue[Dict] = asyncio.Queue()
        self.database: asyncio.Queue[Dict] = asyncio.Queue()
        self.scope = scope
        self.stream_id = stream_id
        self.ustream_id = None
        self.transmit = transmit
        self.autoremove = autoremove
        self.compression = False
        self.partial_pkts = {}

    def process_pkt(self, event):
        if not self.compression:
            partial_event_data = self.partial_pkts.get(event.stream_id)
            if not event.stream_ended:
                if not partial_event_data:
                    self.partial_pkts.update({event.stream_id: event.data})
                else:
                    partial_event_data += event.data
                    self.partial_pkts.update({event.stream_id: partial_event_data})
                return
            if partial_event_data:
                event.data = partial_event_data + event.data
                self.partial_pkts.pop(event.stream_id)
        self.queue.put_nowait(
            {
                "data": event.data,
                "stream": event.stream_id,
                "type": "webtransport.stream.receive",
            }
        )

    def http_event_received(self, event: Union[QuicEvent, H3Event]) -> None:
        if not self.closed:
            if self.accepted:
                if isinstance(event, DatagramReceived):
                    self.queue.put_nowait(
                        {
                            "data": event.data,
                            "type": "webtransport.datagram.receive",
                        }
                    )
                elif isinstance(event, WebTransportStreamDataReceived):
                    self.process_pkt(event)
                elif isinstance(event, ConnectionTerminated) or (isinstance(event, DataReceived) and  event.stream_ended == True):
                    self.closed = True
                    self.queue.put_nowait(
                    {
                        "type": "webtransport.stream.end",
                    }
                    )
                    self.autoremove(self.stream_id)
            else:
                # delay event processing until we get `webtransport.accept`
                # from the ASGI application
                self.http_event_queue.append(event)

    async def run_asgi(self, app: AsgiApplication) -> None:
        self.queue.put_nowait({"type": "webtransport.connect"})
        params = {}
        list = self.scope.get('query_string').decode().split('&')
        for item in list:
            key, val = item.split('=')
            params.update([(key, val)])
        self.compression = (params.get('compression', '') == 'zlib')
        try:
            await app(db, self.scope, params, self.queue, self.send)
        except Exception as e:
            pass
        finally:
            if not self.closed:
                await self.send({"type": "webtransport.close"})

    async def receive(self) -> Dict:
        return await self.queue.get()

    async def send(self, message: Dict) -> None:
        data = b""
        end_stream = False

        if message["type"] == "webtransport.accept":
            self.accepted = True

            headers = [
                (b":status", b"200"),
                (b"server", SERVER_NAME.encode()),
                (b"date", formatdate(time.time(), usegmt=True).encode()),
                (b"sec-webtransport-http3-draft", b"draft02"),
            ]
            self.connection.send_headers(stream_id=self.stream_id, headers=headers)

            # consume backlog
            while self.http_event_queue:
                self.http_event_received(self.http_event_queue.popleft())
        elif message["type"] == "webtransport.close":
            if not self.accepted:
                self.connection.send_headers(
                    stream_id=self.stream_id, headers=[(b":status", b"400")]
                )
            end_stream = True
        elif message["type"] == "webtransport.refuse":
            if not self.accepted:
                self.connection.send_headers(
                    stream_id=self.stream_id, headers=[(b":status", b"401")]
                )
            end_stream = True
        elif message["type"] == "webtransport.datagram.send":
            self.connection.send_datagram(flow_id=self.stream_id, data=message["data"])
        elif message["type"] == "webtransport.stream.send":
            stream_id = self.connection.create_webtransport_stream(self.stream_id, True)
            self.connection._quic.send_stream_data(
                stream_id=stream_id, data=message["data"], end_stream=True
            )

            message["stream"]=stream_id
            message["type"]="webtransport.stream.send"

        elif message["type"] == "webtransport.keepstream.send":
            if not self.ustream_id:
                self.ustream_id = self.connection.create_webtransport_stream(self.stream_id, True)
            self.connection._quic.send_stream_data(
                stream_id=self.ustream_id, data=message["data"], end_stream=False
            )

            message["stream"]=self.ustream_id
            message["type"]="webtransport.keepstream.send"

        if data or end_stream:
            self.connection.send_data(
                stream_id=self.stream_id, data=data, end_stream=end_stream
            )
        if end_stream:
            self.closed = True
            self.autoremove(self.stream_id)
        self.transmit()


Handler = WebTransportHandler


class HttpServerProtocol(QuicConnectionProtocol):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._handlers: Dict[int, Handler] = {}
        self._http: Optional[HttpConnection] = None

    def http_event_received(self, event: H3Event) -> None:
        if isinstance(event, HeadersReceived) and event.stream_id not in self._handlers:
            user = None
            password = None
            authority = None
            headers = []
            http_version = "0.9" if isinstance(self._http, H0Connection) else "3"
            raw_path = b""
            method = ""
            protocol = None
            for header, value in event.headers:
                if header == b":authority":
                    authority = value
                    if len(credentials:=authority.decode().split('@')) > 1:
                        user,password = credentials[0].split(':')
                    headers.append((b"host", value))
                elif header == b":method":
                    method = value.decode()
                elif header == b":path":
                    raw_path = value
                elif header == b":protocol":
                    protocol = value.decode()
                elif header and not header.startswith(b":"):
                    headers.append((header, value))

            if b"?" in raw_path:
                path_bytes, query_string = raw_path.split(b"?", maxsplit=1)
            else:
                path_bytes, query_string = raw_path, b""
            path = path_bytes.decode()
            self._quic._logger.info("HTTP request %s %s", method, path)

            # FIXME: add a public API to retrieve peer address
            client_addr = self._http._quic._network_paths[0].addr
            client = (client_addr[0], client_addr[1])

            handler: Handler
            scope: Dict
            if method == "CONNECT" and protocol == "webtransport":
                scope = {
                    "client": client,
                    "user": user,
                    "password": password,
                    "headers": headers,
                    "http_version": http_version,
                    "method": method,
                    "path": path,
                    "query_string": query_string,
                    "raw_path": raw_path,
                    "root_path": "",
                    "scheme": "https",
                    "type": "webtransport",
                }
                handler = WebTransportHandler(
                    connection=self._http,
                    scope=scope,
                    stream_id=event.stream_id,
                    transmit=self.transmit,
                    autoremove=self.close_handler,
                )
            self._handlers[event.stream_id] = handler
            asyncio.ensure_future(handler.run_asgi(application))
        elif (
            isinstance(event, (DataReceived, HeadersReceived))
            and event.stream_id in self._handlers
        ):
            handler = self._handlers[event.stream_id]
            handler.http_event_received(event)
        elif isinstance(event, DatagramReceived):
            handler = self._handlers[event.flow_id]
            handler.http_event_received(event)
        elif isinstance(event, WebTransportStreamDataReceived):
            handler = self._handlers[event.session_id]
            handler.http_event_received(event)

    def quic_event_received(self, event: QuicEvent) -> None:

        if isinstance(event, ProtocolNegotiated):
            if event.alpn_protocol in H3_ALPN:
                self._http = H3Connection(self._quic, enable_webtransport=True)
            elif event.alpn_protocol in H0_ALPN:
                self._http = H0Connection(self._quic)
        elif isinstance(event, DatagramFrameReceived):
            if event.data == b"quack":
                self._quic.send_datagram_frame(b"quack-ack")
        elif isinstance(event, ConnectionTerminated):
            handlers = self._handlers.copy()
            for handler in handlers.values():
                handler.http_event_received(event)

        #  pass event to the HTTP layer
        if self._http is not None:
            for http_event in self._http.handle_event(event):
                self.http_event_received(http_event)


    def close_handler(self, stream_id: int) -> None:
        self._handlers.pop(stream_id)
        return

class SessionTicketStore:
    """
    Simple in-memory store for session tickets.
    """

    def __init__(self) -> None:
        self.tickets: Dict[bytes, SessionTicket] = {}

    def add(self, ticket: SessionTicket) -> None:
        self.tickets[ticket.ticket] = ticket

    def pop(self, label: bytes) -> Optional[SessionTicket]:
        return self.tickets.pop(label, None)


def exit_program(signum, frame):
    close_event.set()


async def main(
    host: str,
    port: int,
    configuration: QuicConfiguration,
    session_ticket_store: SessionTicketStore,
    retry: bool
) -> None:
    
    close_task = asyncio.create_task(close_event.wait())
    server = await serve(
        host,
        port,
        configuration=configuration,
        create_protocol=HttpServerProtocol,
        session_ticket_fetcher=session_ticket_store.pop,
        session_ticket_handler=session_ticket_store.add,
        retry=retry,
    )
    try:
        await close_task
    finally:
        server.close()


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="QUIC server")

    parser.add_argument(
        "app",
        type=str,
        nargs="?",
        default="demo:app",
        help="the ASGI application as <module>:<attribute>",
    )

    parser.add_argument(
        "--db",
        type=str,
        required=True,
        help="path to file containing SQL database",
    )

    parser.add_argument(
        "-c",
        "--certificate",
        type=str,
        required=True,
        help="load the TLS certificate from the specified file",
    )

    parser.add_argument(
        "--host",
        type=str,
        default="::",
        help="listen on the specified address (defaults to ::)",
    )

    parser.add_argument(
        "--port",
        type=int,
        default=4433,
        help="listen on the specified port (defaults to 4433)",
    )

    parser.add_argument(
        "-k",
        "--private-key",
        type=str,
        help="load the TLS private key from the specified file",
    )

    parser.add_argument(
        "-l",
        "--secrets-log",
        type=str,
        help="log secrets to a file, for use with Wireshark",
    )

    parser.add_argument(
        "-q",
        "--quic-log",
        type=str,
        help="log QUIC events to QLOG files in the specified directory",
    )

    parser.add_argument(
        "--retry",
        action="store_true",
        help="send a retry for new connections",
    )

    parser.add_argument(
        "-v", "--verbose", action="store_true", help="increase logging verbosity"
    )
    
    args = parser.parse_args()

    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        level=logging.DEBUG if args.verbose else logging.INFO,
    )

    # import ASGI application
    module_str, attr_str = args.app.split(":", maxsplit=1)
    spec=importlib.util.spec_from_file_location(module_str, module_str)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    application = getattr(module, attr_str)
    init_application = getattr(module, "init")

    db = SQLDatabase(args.db)

    # create QUIC logger
    if args.quic_log:
        quic_logger = QuicFileLogger(args.quic_log)
    else:
        quic_logger = None

    # open SSL log file
    if args.secrets_log:
        secrets_log_file = open(args.secrets_log, "a")
    else:
        secrets_log_file = None

    configuration = QuicConfiguration(
        alpn_protocols=H3_ALPN + H0_ALPN + ["siduck"],
        is_client=False,
        max_datagram_frame_size=65536,
        quic_logger=quic_logger,
        secrets_log_file=secrets_log_file,
    )

    # load SSL certificate and key
    configuration.load_cert_chain(args.certificate, args.private_key)
    configuration.idle_timeout = 7200

    if uvloop is not None:
        uvloop.install()

    try:
        close_event = asyncio.Event()
        signal.signal(signal.SIGINT, exit_program)
        asyncio.run(db.connect(), debug=True)
        asyncio.run(init_application(db), debug=True)
        sys.stdout.flush()
        asyncio.run(
            main(
                host=args.host,
                port=args.port,
                configuration=configuration,
                session_ticket_store=SessionTicketStore(),
                retry=args.retry,
            ), debug=True
        )
    finally:
        asyncio.run(db.close())
