import logging, argparse, asyncio, importlib, signal, time, sys, json
from aiocoap import *
from pathlib import Path

try:
    import uvloop
except ImportError:
    uvloop = None

sys.path.append("../util/") # absolute path to util's folder
from util import printflush


class Service:
    def __init__(self, params: dict, is_pub: bool) -> None:

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

        self.topic = params.get('topic')
        self.is_pub = is_pub



class COAPClient:
    def __init__(
        self,
        protocol,
        service: Service,
        uri = None,
    ) -> None:
        self.uri = uri
        self.protocol = protocol
        self.service = service
        self.queue: asyncio.Queue[dict] = asyncio.Queue()
        self.app_task = None
        self.subscription = None
        self.close_task = asyncio.create_task(close_event.wait())
        

    async def run_asgi(self, app: callable) -> None:
        try:
            if self.service.is_pub:
                printflush("**%s, %s, CONNECTED_PUBLISHER, %s, %d" % (time.time_ns(), self.service.topic, None, 0))
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
            res = self.protocol.request(Message(code=PUT, payload=message, uri=self.uri, content_format=0)).response
            await asyncio.wait(
                    [res, self.close_task],
                    return_when=asyncio.FIRST_COMPLETED)
        except:
            pass


    async def finish_app(self) -> None:
        if self.subscription is not None:
            self.queue.put_nowait(
                {
                    "exit": True
                }
            )
            try:
                await asyncio.wait_for(self.subscription, 5)
            except:
                pass
            try:
                await asyncio.wait_for(self.unsubscribe(self.uri), 5)
            except:
                pass
        await asyncio.wait_for(self.app_task, None)


    async def close(self) -> None:
        close_event.set()
        return
    

    async def connect(self, uri=None):
        event = "CONNECTING_PUBLISHER" if self.service.is_pub else "CONNECTING_SUBSCRIBER"
        printflush("**%s, %s, %s, %s, %d" % (time.time_ns(), self.service.topic, event, None, 0))
        if uri is not None:
            self.uri = uri
        self.app_task = asyncio.ensure_future(self.run_asgi(self.service.application))
        if not self.service.is_pub:
            self.subscription = asyncio.ensure_future(self.subscribe(self.uri)) 
    
    async def get_observation(self, iter):
        res = await anext(iter)
        return res

    async def subscribe(self, uri):
        try:
            changes = None
            request = self.protocol.request(Message(code=GET, uri=uri, observe=0))
            changes = await self.recieve_response(request)
            it = aiter(request.observation)

            while(True):
                changes_task = asyncio.create_task(self.get_observation(it))
                await asyncio.wait(
                        [changes_task, self.close_task],
                        return_when=asyncio.FIRST_COMPLETED)
                if close_event.is_set():
                    break
                observation = changes_task.result()
                if observation.payload:
                    self.queue.put_nowait(
                        {
                            "data": observation.payload,
                            "code": observation.code,
                            "exit": False,
                        }
                    )
        except:
            pass
        finally:
            if changes is not None:   
                request.observation.cancel()

    async def unsubscribe(self, uri):
        try:
            response = await self.protocol.request(Message(code=GET, uri=uri, observe=1)).response
        except:
            pass

    async def recieve_response(self, sent_request):
        response = await sent_request.response
        printflush("**%s, %s, CONNECTED_SUBSCRIBER, %s, %d" % (time.time_ns(), self.service.topic, None, 0))
        if response.payload:
            self.queue.put_nowait(
                {
                    "data": response.payload,
                    "code": response.code,
                    "exit": False,
                }
            )
        return response


    async def shutdown(self):
        if self.app_task is not None:
            await self.finish_app()
        event = "CLOSED_PUBLISHER" if self.service.is_pub else "CLOSED_SUBSCRIBER"
        printflush("**%s, %s, %s, %s, %d" % (time.time_ns(), self.service.topic, event, None, 0))



def exit_program(signum, frame):
    close_event.set()


async def main(
    credentials: Path,
    host: str,
    port: int,
    path: str,
    service: Service
) -> None:
    
    #protocol = await Context.create_client_context(transports=['tlsclient'])
    protocol = await Context.create_client_context()
    if credentials:
        protocol.client_credentials.load_from_dict(json.load(credentials.open('rb')))
    uri = "coap://" + host + ":" + str(port) + "/" + path
    COAPclient = COAPClient(protocol, service)
    
    await COAPclient.connect(uri)
    await close_event.wait()
    await COAPclient.shutdown()
    try:
        await protocol.shutdown()
    except:
        pass


def validate_parameters(parser: 'ArgumentParser', parameters: dict, is_pub: bool) -> None:
    '''
    if parameters.get('app') is None or parameters.get('topic') is None or int(parameters.get('qos')) not in [0,1,2]:
        parser.error("BAD PARAMETERS")
    '''
    return



if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="COAP client")
    
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
        "-c",
        "--credentials",
        type=Path,
        required=False,
        help="load the TLS certificate from the specified file",
    )

    parser.add_argument(
        "--path", 
        type=str, 
        required=True,
        help="uri path"
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
        close_event = asyncio.Event()
        signal.signal(signal.SIGINT, exit_program)
        asyncio.run(
            main(
                credentials=args.credentials,
                host=args.host,
                port=args.port,
                path=args.path,
                service=service,
            )
        )
    except KeyboardInterrupt:
        pass