import argparse, asyncio, logging, ssl, time, importlib, signal, zlib, sys, aioquic
from collections import deque
from typing import Callable, Deque, Dict, List, Union, cast
from urllib.parse import urlparse

import wsproto.events
from aioquic.asyncio.client import connect
from aioquic.asyncio.protocol import QuicConnectionProtocol
from aioquic.h0.connection import H0_ALPN, H0Connection
from aioquic.h3.connection import H3_ALPN, ErrorCode, H3Connection
from aioquic.h3.events import (
    DataReceived,
    H3Event,
    HeadersReceived,
    WebTransportStreamDataReceived,
    DatagramReceived
)
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import QuicEvent, DatagramFrameReceived, ProtocolNegotiated, ConnectionTerminated, PingAcknowledged
from aioquic.quic.logger import QuicFileLogger
from aioquic.tls import CipherSuite

from email.utils import formatdate
try:
    import uvloop
except ImportError:
    uvloop = None

sys.path.append("../util/") # absolute path to util's folder
from util import printflush, Z_WBITS, Z_END_PATTERN

logger = logging.getLogger("client")

AsgiApplication = Callable

USER_AGENT = "aioquic/" + aioquic.__version__


class URL:
    def __init__(self, url: str) -> None:
        parsed = urlparse(url)

        self.authority = parsed.netloc
        self.full_path = parsed.path or "/"
        if parsed.query:
            self.full_path += "?" + parsed.query
        self.scheme = parsed.scheme


class NEvent(asyncio.Event):
    def __init__(self, n_event_set: int) -> None:
        self.n_event_set = n_event_set
        self.captured_sets = 0
        super().__init__()

    def set(self):
        if not self._value:
            self.captured_sets += 1
            if self.captured_sets >= self.n_event_set:
                self._value = True
                for fut in self._waiters:
                    if not fut.done():
                        fut.set_result(True)

    def clear(self):
        self._value = False
        self.captured_sets = 0

    def clear_one(self):
        self._value = False
        self.captured_sets -= 1
    

class Service:
    def __init__(self, user: str|None, password: str|None, host: str, port: int, path: str, params: Dict, is_pub: bool) -> None:

        module_str, attr_str = params.get('app').split(":", maxsplit=1)
        spec=importlib.util.spec_from_file_location(module_str, module_str)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.application = getattr(module, attr_str)
        del params['app']

        self.data = params.get('data')
        if self.data is not None:
            module_str, attr_str = self.data.split(":", maxsplit=1)
            spec=importlib.util.spec_from_file_location(module_str, module_str)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            self.data = getattr(module, attr_str)
            del params['data']
        
        if is_pub:
            params.update([('client', 'publisher')])
        else:
            params.update([('client', 'subscriber')])

        if user is None:
            self.authority = host + ":" + port
        else:
            self.authority = user + ":" + password + "@" + host + ":" + str(port)
        
        self.full_path = path if path.startswith("/") else "/" + path

        self.scheme = "https"

        full_url = self.scheme + "://" + self.authority + self.full_path

        from requests.models import PreparedRequest
        req = PreparedRequest()
        req.prepare_url(full_url, params)
        parsed = urlparse(req.url)

        if parsed.query:
            self.full_path += "?" + parsed.query
        self.protocol = "webtransport"
        self.is_pub = is_pub
        self.compression = params.get('compression')
        self.topic = params.get('topic')
        


class WebTransportHandler:
    def __init__(
        self,
        *,
        connection: H3Connection,
        service: Service,
        stream_id: int,
        transmit: Callable[[], None],
        autoremove: Callable
    ) -> None:
        self.accepted = False
        self.closed = False
        self.connection = connection
        self.http_event_queue: Deque[DataReceived] = deque()
        self.queue: asyncio.Queue[Dict] = asyncio.Queue()
        self.service = service
        self.stream_id = stream_id
        self.ustream_id = None
        self.transmit = transmit
        self.autoremove = autoremove
        self.app_task = None
        self.close_event = asyncio.Event()
        self.compressor = self.decompressor = None
        self.partial_pkts = {}

        if self.service.compression is not None and self.service.compression == 'zlib':
            if service.is_pub:
                self.compressor = zlib.compressobj(zlib.Z_DEFAULT_COMPRESSION, zlib.DEFLATED, Z_WBITS)
            else:
                self.decompressor = zlib.decompressobj(Z_WBITS)

    def process_pkt(self, event):
        if self.decompressor is None:
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
                    self.close_event.set()
                    self.queue.put_nowait(
                    {
                        "type": "webtransport.stream.end",
                    }
                    )
            else:
                # delay event processing until we get `webtransport.accept`
                # from the ASGI application
                self.http_event_queue.append(event)

    def activate(self) -> None:
        self.accepted = True
        while self.http_event_queue:
            event = self.http_event_queue.popleft()
            self.http_event_received(event)

    async def run_asgi(self) -> None:
        event = "CONNECTED_PUBLISHER" if self.service.is_pub else "CONNECTED_SUBSCRIBER"
        printflush("**%s, %s, %s, %s, %d" % (time.time_ns(), self.service.topic, event, None, 0))
        try:
            if self.service.is_pub:
                await self.service.application(self.send, self.close_event, self.service.data, {"topic": self.service.topic})
            else:
                await self.service.application(self.receive, {"topic": self.service.topic})
        finally:
            await self.close()
            await self.autoremove(self.stream_id)

    async def receive(self) -> Dict:
        orig_data = b''
        while(True):
            message = await self.queue.get()
            if message.get('data') is not None and self.decompressor is not None:
                orig_data += message['data']
                while(orig_data):
                    index = orig_data.find(Z_END_PATTERN)
                    if index != -1:
                        index += len(Z_END_PATTERN)
                        cdata = orig_data[0:index]
                        try:
                            dec = self.decompressor.decompress(cdata)
                            dec += self.decompressor.flush()
                        except:
                            import traceback
                            traceback.print_exc(file=sys.stdout)
                            sys.stdout.flush()
                        orig_data = orig_data[index:]
                        message['data'] = dec
                        yield message
                    else:
                        break
            else:
                yield message

    async def send(self, message: Dict) -> None:
        data = message.get('data')
        if data is not None and self.compressor is not None:
            if message["type"] == "webtransport.stream.send":
                message["type"] = "webtransport.keepstream.send"
            data = self.compressor.compress(message['data'])
            data += self.compressor.flush(zlib.Z_SYNC_FLUSH)
        end_stream = False

        if message["type"] == "webtransport.accept":
            self.accepted = True

            headers = [
                (b":status", b"200"),
                (b"server", "SERVER_NAME".encode()),
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
                    stream_id=self.stream_id, headers=[(b":status", b"403")]
                )
            end_stream = True
        elif message["type"] == "webtransport.datagram.send":
            self.connection.send_datagram(flow_id=self.stream_id, data=data)
        elif message["type"] == "webtransport.stream.send":
            stream_id = self.connection.create_webtransport_stream(self.stream_id, True)
            self.connection._quic.send_stream_data(
                stream_id=stream_id, data=data, end_stream=True
            )
        elif message["type"] == "webtransport.keepstream.send":
            if not self.ustream_id:
                self.ustream_id = self.connection.create_webtransport_stream(self.stream_id, True)
            self.connection._quic.send_stream_data(
                stream_id=self.ustream_id, data=data, end_stream=False
            )
        if end_stream:
            self.connection.send_data(
                stream_id=self.stream_id, data=data, end_stream=end_stream
            )
            self.closed = True
            self.autoremove(self.stream_id)
        self.transmit()


    async def close(self, forced: bool = False) -> None:
        if not self.closed:
            self.connection.send_data(stream_id=self.stream_id, data=b'', end_stream=True)
            self.transmit()
            self.closed = True
        event = "CLOSED_PUBLISHER" if self.service.is_pub else "CLOSED_SUBSCRIBER"
        printflush("**%s, %s, %s, %s, %d" % (time.time_ns(), self.service.topic, event, None, 0))


    async def finish(self) -> None:
        self.queue.put_nowait(
            {
                "type": "webtransport.stream.end",
            }
        )
        self.close_event.set()
        if self.app_task:
            await asyncio.wait_for(self.app_task, None)
    


Handler = WebTransportHandler


class HttpClientProtocol(QuicConnectionProtocol):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._handlers: Dict[int, Handler] = {}
        self._http: H3Connection = None
        self._request_events: List[int] = []
        self._request_waiter: Dict[int, asyncio.Future[Deque[H3Event]]] = {}
        self.keepalive_timeout = self._quic.configuration.idle_timeout*1/10
        self.keepalive_task = None
        self.keepalive_active = False
        self.closed = False

    def transmit(self) -> None:
        self.restart_keepalive()
        return super().transmit()

    async def keepalive(self) -> None:
        while (True):
            await asyncio.sleep(self.keepalive_timeout)
            await self.ping()

    def restart_keepalive(self) -> None:
        if self.keepalive_active:
            if self.keepalive_task:
                self.keepalive_task.cancel()
            self.keepalive_task = asyncio.ensure_future(self.keepalive())

    def http_event_received(self, event: H3Event) -> None:
        if isinstance(event, HeadersReceived) and event.stream_id in self._request_events:
            for header, value in event.headers:
                if header == b':status':
                    if value == b'200':
                        self._request_events.remove(event.stream_id)
                        handler = self._handlers[event.stream_id]
                        request_waiter = self._request_waiter.pop(event.stream_id)
                        request_waiter.set_result(event)
                        handler.activate()
                        handler.app_task = asyncio.ensure_future(handler.run_asgi())
                        self.keepalive_active = True
                        self.restart_keepalive()
                    else:
                        request_waiter = self._request_waiter.pop(event.stream_id)
                        request_waiter.set_result(event)
                        close_event.set()

        elif isinstance(event, (DataReceived, HeadersReceived)) and event.stream_id in self._handlers:
            handler = self._handlers[event.stream_id]
            handler.http_event_received(event)

        elif isinstance(event, DatagramReceived) and event.flow_id in self._handlers:
            handler = self._handlers[event.flow_id]
            handler.http_event_received(event)

        elif isinstance(event, WebTransportStreamDataReceived) and event.session_id in self._handlers:
            handler = self._handlers[event.session_id]
            handler.http_event_received(event)

    def quic_event_received(self, event: QuicEvent) -> None:
        self.restart_keepalive()
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

        if self._http is not None:
            for http_event in self._http.handle_event(event):
                self.http_event_received(http_event)


    async def close_handler(self, stream_id: int) -> None:
        self._handlers.pop(stream_id)
        close_event.set()
    

    async def shutdown(self):
        self.closed = True
        handlers = self._handlers.copy()
        for handler in handlers.values():
            await handler.finish()
        if self.keepalive_active:
            self.keepalive_active = False
            self.keepalive_task.cancel()
            try:
                await asyncio.wait_for(self.keepalive_task, None)
            except:
                pass


    async def connectwt(self, service: Service, ts: int, close_task: 'task') -> None:
        stream_id = self._quic.get_next_available_stream_id()

        handler = WebTransportHandler(
            connection=self._http,
            service=service,
            stream_id=stream_id,
            transmit=self.transmit,
            autoremove=self.close_handler
        )
        self._handlers[stream_id] = handler

        self._http.send_headers(
            stream_id=stream_id,
            headers=[
                (b":method", b"CONNECT"),
                (b":scheme", service.scheme.encode()),
                (b":authority", service.authority.encode()),
                (b":path", service.full_path.encode()),
                (b":protocol", service.protocol.encode()),
            ],
        )

        waiter = self._loop.create_future()
        self._request_events.append(stream_id)
        self._request_waiter[stream_id] = waiter
        
        self.transmit()


        await asyncio.wait(
            [waiter, close_task],
            return_when=asyncio.FIRST_COMPLETED)
        if close_event.is_set():
            event = "CLOSED_PUBLISHER" if service.is_pub else "CLOSED_SUBSCRIBER"
            printflush("**%s, %s, %s, %s, %d" % (time.time_ns(), service.topic, event, None, 0))
            return
        result = waiter.result()

        if result.headers[0][1] != b'200':
            event = "REFUSED_PUBLISHER" if service.is_pub else "REFUSED_SUBSCRIBER"
            printflush("**%s, %s, %s, %s, %d" % (time.time_ns(), service.topic, event, None, 0))
            event = "CLOSED_PUBLISHER" if service.is_pub else "CLOSED_SUBSCRIBER"
            printflush("**%s, %s, %s, %s, %d" % (time.time_ns(), service.topic, event, None, 0))
        return
 

def exit_program(signum, frame):
    for i in range(len(services)):
        close_event.set()
    if not quic_connected:
        for service in services:
            event = "CLOSED_PUBLISHER" if service.is_pub else "CLOSED_SUBSCRIBER"
            printflush("**%s, %s, %s, %s, %d" % (time.time_ns(), service.topic, event, None, 0))
        loop = asyncio.get_event_loop()
        loop.call_soon_threadsafe(loop.stop)
        sys.exit(0)


async def main(
    configuration: QuicConfiguration,
    host: str,
    port: int,
    services: List[Service],
    local_port: int,
) -> None:
    try:
        ts = time.time_ns()
        close_task = asyncio.create_task(close_event.wait())
        for service in services:
            event = "CONNECTING_PUBLISHER" if service.is_pub else "CONNECTING_SUBSCRIBER"
            printflush("**%s, %s, %s, %s, %d" % (ts, service.topic, event, None, 0))

        async with connect(
            host=host,
            port=port,
            configuration=configuration,
            create_protocol=HttpClientProtocol,
            local_port=local_port,
        ) as client:
            global quic_connected
            quic_connected = True
            client = cast(HttpClientProtocol, client)
            coros = [
                client.connectwt(service, ts, close_task)
                for service in services
            ]
            await asyncio.gather(*coros)
            try:
                await close_task
            finally:
                await client.shutdown()
    except Exception as e:
        import traceback
        traceback.print_exc()


def validate_parameters(parser: 'ArgumentParser', parameters: Dict, is_pub: bool) -> None:
    #parser.error("BAD PARAMETERS")
    return



if __name__ == "__main__":
    defaults = QuicConfiguration(is_client=True)

    parser = argparse.ArgumentParser(description="HTTP/3 client")
    
    parser.add_argument(
        "--sub",
        type=str,
        action='append',
        nargs='+',
        metavar="'key=value', 'key=value', ...",
        help="parameters",
    )

    parser.add_argument(
        "--pub",
        type=str,
        action='append',
        nargs='+',
        metavar="'key=value', 'key=value', ...",
        help="parameters",
    )

    parser.add_argument(
        "--user", 
        type=str, 
        help="auth user"
    )

    parser.add_argument(
        "--password", 
        type=str, 
        help="auth password"
    )

    parser.add_argument(
        "--host", 
        type=str, 
        required=True,
        help="destination host"
    )

    parser.add_argument(
        "--port", 
        type=int, 
        required=True,
        help="destination port"
    )

    parser.add_argument(
        "--path", 
        type=str, 
        required=True,
        help="url path"
    )

    parser.add_argument(
        "--ca-certs", 
        type=str, 
        help="load CA certificates from the specified file"
    )

    parser.add_argument(
        "--cipher-suites",
        type=str,
        help="only advertise the given cipher suites, e.g. `AES_256_GCM_SHA384,CHACHA20_POLY1305_SHA256`",
    )

    parser.add_argument(
        "--max-data",
        type=int,
        help="connection-wide flow control limit (default: %d)" % defaults.max_data,
    )

    parser.add_argument(
        "--max-stream-data",
        type=int,
        help="per-stream flow control limit (default: %d)" % defaults.max_stream_data,
    )

    parser.add_argument(
        "--max-datagram-frame-size",
        type=int,
        help="per-datagram frame size limit (default: %d)" % 65515,
    )

    parser.add_argument(
        "-k",
        "--insecure",
        action="store_true",
        help="do not validate server certificate",
    )
     
    parser.add_argument(
        "-l",
        "--secrets-log",
        type=str,
        help="log secrets to a file, for use with Wireshark",
    )
   
    parser.add_argument(
        "-v", 
        "--verbose", 
        action="store_true", 
        help="increase logging verbosity"
    )

    parser.add_argument(
        "--local-port",
        type=int,
        default=0,
        help="local port to bind for connections",
    )

    args = parser.parse_args()

    if args.pub is None and args.sub is None:
        parser.error("At least one of the followings arguments is required: --pub --sub")
    if args.user is not None and args.password is None:
        parser.error("--password has not been provided")
    if args.user is None and args.password is not None:
        parser.error("--user has not been provided")

    subdicts = []
    pubdicts = []
    services = []

    if args.pub is not None:
        for list in args.pub:
            newdict = dict()
            for item in list:
                key, val = item.split('=')
                newdict.update([(key, val)])
            validate_parameters(parser, newdict, True)
            pubdicts.append(newdict)

    if args.sub is not None:
        for list in args.sub:
            newdict = dict()
            for item in list:
                key, val = item.split('=')
                newdict.update([(key, val)])
            validate_parameters(parser, newdict, False)
            subdicts.append(newdict)

    for item in pubdicts:
        services.append(Service(args.user, args.password, args.host, args.port, args.path, item, True))

    for item in subdicts:
        services.append(Service(args.user, args.password, args.host, args.port, args.path, item, False))

    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        level=logging.DEBUG if args.verbose else logging.INFO,
    )


    # prepare configuration
    configuration = QuicConfiguration(
        is_client=True, alpn_protocols=H3_ALPN
    )
    if args.ca_certs:
        configuration.load_verify_locations(args.ca_certs)
    if args.cipher_suites:
        configuration.cipher_suites = [
            CipherSuite[s] for s in args.cipher_suites.split(",")
        ]
    if args.insecure:
        configuration.verify_mode = ssl.CERT_NONE
    if args.max_data:
        configuration.max_data = args.max_data
    if args.max_stream_data:
        configuration.max_stream_data = args.max_stream_data
    if args.max_datagram_frame_size:
        configuration.max_datagram_frame_size = args.max_datagram_frame_size
    else:
        configuration.max_datagram_frame_size = 65515

    if uvloop is not None:
        uvloop.install()

    configuration.idle_timeout = 7200
    try:
        close_event = NEvent(len(services))
        quic_connected = False
        signal.signal(signal.SIGINT, exit_program)
        asyncio.run(
            main(
                configuration=configuration,
                host=args.host,
                port=args.port,
                services=services,
                local_port=args.local_port,
            )
        )
    except KeyboardInterrupt:
        pass

