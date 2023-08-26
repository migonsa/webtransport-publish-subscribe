import asyncio, zlib, sys
from typing import Callable, Dict, List, Tuple

sys.path.append("../util/") # absolute path to util's folder
from util import printflush, Z_WBITS, Z_END_PATTERN


class SubscriberQueue:
    def __init__(self, queue: asyncio.Queue[Dict]) -> None:
        self.id = None
        self.queue = queue

    def bindId(self, id: int) -> None:
        self.id = id

    def getId(self) -> int:
        return self.id

    def setId(self, id: int) -> None:
        self.id = id

    def getQueue(self) -> asyncio.Queue[Dict]:
        return self.queue


class Group:
    def __init__(self, wbits: int = Z_WBITS) -> None:
        self.compressor = zlib.compressobj(zlib.Z_DEFAULT_COMPRESSION, zlib.DEFLATED, wbits)
        self.wbits = wbits
        self.bytes = 0
        self.members = 0
        self.output = None

    def compress(self, message: str) -> None:
        data = self.compressor.compress(message)
        data += self.compressor.flush(zlib.Z_SYNC_FLUSH)
        self.bytes += len(message)
        self.output = data

    def getOutput(self) -> bytes:
        return self.output

    def isMergeable(self) -> bool:
        return self.bytes > pow(2, abs(self.wbits))

    def isNew(self) -> bool:
        return self.bytes == 0

    def isEmpty(self) -> bool:
        return self.members == 0

    def addMember(self) -> None:
        self.members += 1

    def deleteMember(self) -> None:
        self.members -= 1


class PS:
    def __init__(self, db):
        self.db = db
        self.groups: Dict[int, Group] = {}
        self.queues: List[SubscriberQueue] = []
        self.topics: Dict[str, Tuple[Dict[int, Group], List[SubscriberQueue], Dict]] = {}

    async def fill_topics(self):
        topics = await self.db.get_topics()
        for topic in topics:
            self.topics[topic] = ({},[],{})
    
    async def check_publisher(self, user, password, topic):
        return await self.db.check_publisher(user, password, topic)

    async def check_subscriber(self, user, password, topic):
        return await self.db.check_subscriber(user, password, topic)

    def assign_group(self, topic: str, compressor: bool) -> Tuple[int, Group]:
        if compressor:
            d = self.topics[topic][0]
            dlen = len(d)
            if dlen == 0:
                d[0] = Group()
            for item in d.items():
                if item[1].isNew():
                    return (item[0], item[1])
            d[item[0]+1] = Group()
            return (item[0]+1, d[item[0]+1])
        else:
            return (None, None)

    def merge2group0(self, topic: str, subscriber: SubscriberQueue) -> None:
        id = subscriber.getId()
        subscriber.setId(0)
        self.topics[topic][0][id].deleteMember()
        self.topics[topic][0][0].addMember()
        printflush("%s: MERGED SUB ID_GROUP=%d TOTAL_MEMBERS=%d GP0_MEMBERS=%d" % (topic, id, self.topics[topic][0][id].members, self.topics[topic][0][0].members))
        if self.topics[topic][0][id].isEmpty():
            self.topics[topic][0].pop(id, None)
            printflush("%s: DELETED ID_GROUP=%d" % (topic, id))
        return

    def new_subscriber(self, topic: str, subscriber: SubscriberQueue, compressor: bool) -> None:
        if topic in self.topics:
            id,group = self.assign_group(topic, compressor)
            if id is not None and group is not None:
                subscriber.bindId(id)
                group.addMember()
                printflush("%s: NEW SUBSCRIBER --> ID_GROUP=%d TOTAL_MEMBERS=%d" % (topic, id, group.members))
            self.topics[topic][1].append(subscriber)
            if len(self.topics[topic][2]) != 0:
                self.copy_first_message(group, subscriber, self.topics[topic][2].copy())
        return

    def copy_first_message(self, group: Group, subscriber: SubscriberQueue, message: Dict):
        raw_data = message['data']
        if group is None:
            subscriber.getQueue().put_nowait(message.copy())
        else:
            group.compress(raw_data)
            message['data'] = group.getOutput()
            subscriber.getQueue().put_nowait(message.copy())
        return

    def delete_subscriber(self, topic: str, subscriber: SubscriberQueue) -> None:
        if topic in self.topics:
            id = subscriber.getId()
            if id is not None:
                group = self.topics[topic][0][id]
                group.deleteMember()
                if group.isEmpty():
                    self.topics[topic][0].pop(id, None)
            self.topics[topic][1].remove(subscriber) 
        return

    def copy(self, topic: str, message: Dict) -> None:
        if topic in self.topics:
            message['type'] = 'webtransport.stream.pubs'
            raw_data = message['data']
            self.topics[topic][2].update({'type':message['type'], 'data':message['data']})
            gpdict = self.topics[topic][0]
            qlist = self.topics[topic][1]
            for gp in gpdict.values():
                gp.compress(raw_data)
            for sub in qlist:
                id = sub.getId()
                if id is not None:
                    message['data'] = gpdict[id].getOutput()
                    sub.getQueue().put_nowait(message.copy())
                    if id != 0 and gpdict[id].isMergeable():
                        self.merge2group0(topic, sub)
                else:
                    message['data'] = raw_data
                    sub.getQueue().put_nowait(message.copy())
        return


ps = None


async def publisher(scope: Dict, params: Dict, queue: asyncio.Queue, send: Callable) -> None:
    message = await queue.get()
    assert message["type"] == "webtransport.connect"

    user = scope['user']
    password = scope['password']
    topic = params.get('topic')
    comp = params.get('compression')

    if comp == 'zlib':
        decompressor = zlib.decompressobj(Z_WBITS)
    else:
        decompressor = None

    if (await ps.check_publisher(user, password, topic)):
        await send({"type": "webtransport.accept"})

        orig_data = b''
        while(True):
            message = await queue.get()
            if message.get('data') is not None:
                if decompressor is not None:
                    orig_data += message['data']
                    while(orig_data):
                        index = orig_data.find(Z_END_PATTERN)
                        if index != -1:
                            index += len(Z_END_PATTERN)
                            cdata = orig_data[0:index]
                            dec = decompressor.decompress(cdata)
                            dec += decompressor.flush()
                            orig_data = orig_data[index:]
                            message['data'] = dec
                            ps.copy(topic, message.copy())
                        else:
                            break
                else:
                    ps.copy(topic, message.copy())
    else:
        await send({"type": "webtransport.refuse"})
    return


async def subscriber(scope: Dict, params: Dict, queue: asyncio.Queue, send: Callable) -> None:
    message = await queue.get()
    assert message["type"] == "webtransport.connect"

    user = scope['user']
    password = scope['password']
    topic = params.get('topic')
    comp = params.get('compression')

    compressor = False
    sendtype = 'webtransport.stream.send'
    if comp == 'zlib':
        compressor = True
        sendtype = 'webtransport.keepstream.send'

    if (await ps.check_subscriber(user, password, topic)):
        await send({"type": "webtransport.accept"})
        me = SubscriberQueue(queue)
        ps.new_subscriber(topic, me, compressor)

        # echo back received data
        while True:
            message = await queue.get()
            if message['type'] == 'webtransport.stream.pubs':
                data = message.get('data')
                await send({
                        "data": data,
                        "type": sendtype,
                        "user": user,
                })
            elif message['type'] == 'webtransport.stream.end':
                ps.delete_subscriber(topic, me)
                break
    else:
        await send({"type": "webtransport.refuse"})
    return


async def init(db: 'SQLDatabase'):
    global ps
    if ps is None:
        ps = PS(db)
        await ps.fill_topics()
    print("INIT DONE!")


async def app(db: 'SQLDatabase', scope: Dict, params: Dict, queue: asyncio.Queue, send: Callable) -> None:
    if scope["type"] == "webtransport":
        client = params.get('client')
        if client == "publisher":
            await publisher(scope, params, queue, send)
        elif client == "subscriber":
            await subscriber(scope, params, queue, send)
