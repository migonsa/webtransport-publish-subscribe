import ssl, logging, argparse, asyncio, importlib, signal, time
from asyncio_paho import AsyncioPahoClient

try:
    import uvloop
except ImportError:
    uvloop = None

import sys
sys.path.append("/home/detraca/TFM/util/")
from util import printflush


class Service:
    def __init__(self, params: dict, is_pub: bool) -> None:

        module_str, attr_str = params.get('app').split(":", maxsplit=1)
        spec=importlib.util.spec_from_file_location(module_str, module_str)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        #module = importlib.import_module(module_str)
        self.application = getattr(module, attr_str)
        del params['app']

        self.data = params.get('data')
        if self.data is not None:
            module_str, attr_str = self.data.split(":", maxsplit=1)
            spec=importlib.util.spec_from_file_location(module_str, module_str)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            #module = importlib.import_module(module_str)
            self.data = getattr(module, attr_str)
            del params['data']

        self.topic = params.get('topic')
        self.qos = int(params.get('qos'))
        self.is_pub = is_pub



class MQTTClient:
    def __init__(
        self,
        client: AsyncioPahoClient,
        service: Service,
    ) -> None:
        client.asyncio_listeners.add_on_connect(self.on_connect)
        client.asyncio_listeners.add_on_connect_fail(self.on_connect_fail)
        client.asyncio_listeners.add_on_message(self.on_message)
        client.asyncio_listeners.add_on_publish(self.on_publish)
        client.asyncio_listeners.add_on_subscribe(self.on_subscribe)
        self.client = client
        self.service = service
        self.queue: asyncio.Queue[dict] = asyncio.Queue()
        self.app_task = None
        self.subscription = None
        self.ever_connected = False
        self.connected = False
        self.close_task = asyncio.create_task(close_event.wait())
    
    
    async def run_asgi(self, app: callable) -> None:
        try:
            if self.service.is_pub:
                await app(self.send, close_event, self.service.data, {"topic": self.service.topic})
            else:
                await app(self.receive, {"topic": self.service.topic})
        finally:
            await self.close()

    async def receive(self) -> dict:
        message = await self.queue.get()
        return message

    async def send(self, message: str) -> None:
        try:
            if self.connected:
                task1 = asyncio.create_task(self.client.asyncio_publish(self.service.topic, message, self.service.qos, retain=True))
                await asyncio.wait(
                    [task1, self.close_task],
                    return_when=asyncio.FIRST_COMPLETED)
        except:
            pass

    async def finish_app(self) -> None:
        if self.subscription is not None:
            self.subscription.cancel()
            try:
                await asyncio.wait_for(self.subscription, None)
            except:
                pass
            self.queue.put_nowait(
                {
                    "exit": True
                }
            )
        await asyncio.wait_for(self.app_task, None)

    async def close(self) -> None:
        close_event.set()
        return
    
    async def connect(self, host, port):
        event = "CONNECTING_PUBLISHER" if self.service.is_pub else "CONNECTING_SUBSCRIBER"
        printflush("**%s, %s, %s, %s, %d" % (time.time_ns(), self.service.topic, event, None, 0))
        while(not self.connected and not close_event.is_set()):
            try:
                task1 = asyncio.create_task(self.client.asyncio_connect(host, port))
                await asyncio.wait(
                    [task1, self.close_task],
                    return_when=asyncio.FIRST_COMPLETED)
            except:
                pass

    async def on_connect_fail(self, flags, rc):
        self.connected = False

    async def on_connect(self, client, userdata, flags, rc):
        if not self.ever_connected:
            self.ever_connected = True
            event = "CONNECTED_PUBLISHER" if self.service.is_pub else "CONNECTED_SUBSCRIBER"
            printflush("**%s, %s, %s, %s, %d" % (time.time_ns(), self.service.topic, event, None, 0))
        self.connected = True
        if not self.app_task or self.app_task._state == 'FINISHED':
            self.app_task = asyncio.ensure_future(self.run_asgi(self.service.application))
        if not self.service.is_pub and (not self.subscription or self.subscription._state == 'FINISHED'):
            self.subscription = asyncio.ensure_future(self.client.asyncio_subscribe(self.service.topic, self.service.qos)) 
            

    
    async def on_message(self, client, userdata, message):
        self.queue.put_nowait(
            {
                "data": message.payload,
                "topic": message.topic,
                "qos": message.qos,
                "exit": False,
            }
        )

    async def shutdown(self):
        if self.app_task is not None:
            await self.finish_app()
        event = "CLOSED_PUBLISHER" if self.service.is_pub else "CLOSED_SUBSCRIBER"
        printflush("**%s, %s, %s, %s, %d" % (time.time_ns(), self.service.topic, event, None, 0))

    async def on_publish(self, client, userdata, mid):
        pass
    async def on_subscribe(self, client, userdata, mid, qos):
        pass


def exit_program(signum, frame):
    close_event.set()


async def main(
    client_id: str,
    ca_certs: str,
    certfile: str,
    keyfile: str,
    insecure: bool,
    host: str,
    port: int,
    service: Service
) -> None:

    client = AsyncioPahoClient(client_id=client_id, clean_session=False)
    client.tls_set(ca_certs=ca_certs, 
                    certfile=certfile, 
                    keyfile=keyfile, 
                    tls_version=ssl.PROTOCOL_TLSv1_2)
    client.tls_insecure_set(insecure)
    MQTTclient = MQTTClient(client, service)
    await MQTTclient.connect(host=host, port=port)
    await close_event.wait()
    await MQTTclient.shutdown()
    client.disconnect()


def validate_parameters(parser: 'ArgumentParser', parameters: dict, is_pub: bool) -> None:
    if parameters.get('app') is None or parameters.get('topic') is None or int(parameters.get('qos')) not in [0,1,2]:
        parser.error("BAD PARAMETERS")
    return



if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="MQTT client")
    
    parser.add_argument(
        "--sub",
        type=str,
        nargs='+',
        metavar="'key=value', 'key=value', ...",
        #required="--pub" not in sys.argv,
        help="parameters",
    )

    parser.add_argument(
        "--pub",
        type=str,
        nargs='+',
        metavar="'key=value', 'key=value', ...",
        #required="--sub" not in sys.argv,
        help="parameters",
    )

    parser.add_argument(
        "--user", 
        type=str,
        default="default",
        help="client-id"
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
        "--ca-certs", 
        type=str,
        required=True,
        help="load CA certificates from the specified file"
    )

    parser.add_argument(
        "--certfile", 
        type=str,
        required=True,
        help="load client certificate from the specified file"
    )

    parser.add_argument(
        "--keyfile", 
        type=str,
        required=True,
        help="load key from the specified file"
    )

    parser.add_argument(
        "-k",
        "--insecure",
        action="store_true",
        help="do not validate server certificate",
    )

    parser.add_argument(
        "-v", 
        "--verbose", 
        action="store_true", 
        help="increase logging verbosity"
    )
     
    args = parser.parse_args()

    if args.pub is None and args.sub is None:
        parser.error("One of the followings arguments is required: --pub --sub")
    elif args.pub is not None and args.sub is not None:
        parser.error("Arguments --pub and --sub are not compatible")

    if args.pub is not None:
        params = dict()
        for item in args.pub:
            key, val = item.split('=')
            params.update([(key, val)])
        validate_parameters(parser, params, True)
        service = Service(params, True)

    elif args.sub is not None:
        params = dict()
        for item in args.sub:
            key, val = item.split('=')
            params.update([(key, val)])
        validate_parameters(parser, params, False)
        service = Service(params, False)

    if uvloop is not None:
        uvloop.install()

    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        level=logging.DEBUG if args.verbose else logging.INFO,
    )

    try:
        client = None
        close_event = asyncio.Event()
        signal.signal(signal.SIGINT, exit_program)
        asyncio.run(
            main(
                client_id=args.user,
                ca_certs=args.ca_certs,
                certfile=args.certfile,
                keyfile=args.keyfile,
                insecure=args.insecure,
                host=args.host,
                port=args.port,
                service=service,
            )
        )
    except KeyboardInterrupt:
        pass
