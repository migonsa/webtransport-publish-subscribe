import logging, asyncio, argparse, importlib, json, aiocoap
import aiocoap.resource as resource
import aiocoap.protocol as protocol

from pathlib import Path
from aiocoap.oscore_sitewrapper import OscoreSiteWrapper
from aiocoap.credentials import CredentialsMap

try:
    import uvloop
except ImportError:
    uvloop = None


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
        self.qos = int(params.get('qos'))
        self.is_pub = is_pub


class CoapProtocol(resource.ObservableResource):

    def __init__(self):
        super().__init__()
        self.content = None
        self.clients = {}
        self.handle = None

    async def add_observation(self, request, serverobservation):
        self._observations.add(serverobservation)
        def _cancel(self=self, obs=serverobservation):
            self._observations.remove(serverobservation)
            self.clients.pop(request.unresolved_remote)
            self.update_observation_count(len(self._observations))
        serverobservation.accept(_cancel)
        self.update_observation_count(len(self._observations))
        self.clients.update({request.unresolved_remote:serverobservation})
     
    def update_observation_count(self, newcount):
        pass

    async def render_get(self, request):
        if self.content is not None:
            return aiocoap.Message(payload=self.content)
        else:
            if request.opt.observe == 1:
                return aiocoap.Message(payload='')
            return aiocoap.Message(no_response=26)

    async def render_put(self, request):
        self.content = request.payload
        if len(self.clients) != 0:
            self.updated_state()
        return aiocoap.Message(code=aiocoap.CHANGED, payload=request.payload)


async def main(
    host: str,
    port: int,
    credentials: Path,
    topics: list[str],
) -> None:

    root = resource.Site()

    for topic in topics:
        root.add_resource([topic], CoapProtocol())

    server_credentials = None
    if credentials:
        server_credentials = CredentialsMap()
        server_credentials.load_from_dict(json.load(credentials.open('rb')))
        root = OscoreSiteWrapper(root, server_credentials)
    await aiocoap.Context.create_server_context(root, bind=(host, port), server_credentials=server_credentials)
    
    try:
        await asyncio.Future()
    except:
        pass



if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="COAP server")

    parser.add_argument(
        "--topics",
        type=str,
        nargs='+',
        metavar="'topic0', 'topic1', ...",
        required=True,
        help="definition of available topics",
    )

    parser.add_argument(
        "-c",
        "--credentials",
        type=Path,
        required=False,
        help="load the TLS certificate from the specified file",
    )

    parser.add_argument(
        "--host",
        type=str,
        default="localhost",
        help="listen on the specified address (defaults to ::)",
    )

    parser.add_argument(
        "--port",
        type=int,
        default=7777,
        help="listen on the specified port (defaults to 4433)",
    )

    parser.add_argument(
        "-v", "--verbose", action="store_true", help="increase logging verbosity"
    )

    args = parser.parse_args()


    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        level=logging.DEBUG if args.verbose else logging.INFO,
    )


    if uvloop is not None:
        uvloop.install()

    try:
        asyncio.run(
            main(
                host=args.host,
                port=args.port,
                credentials=args.credentials,
                topics=args.topics,
            )
        )
    except KeyboardInterrupt:
        pass