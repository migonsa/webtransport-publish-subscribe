import asyncio, time, sys
from fnvhash import fnv1a_32 as fnvhash32
sys.path.append("../util/") # absolute path to util's folder
from util import printflush


async def webtransport_subscribe(receive: callable, debug: dict = None) -> None:
    async for message in receive():
        recv_data = message.get('data')
        if recv_data is not None:
            if debug:
                printflush("**%s, %s, RECIEVED, %s, %d" % (time.time_ns(), debug.get('topic'), fnvhash32(recv_data), len(recv_data)))
        elif message['type'] == 'webtransport.stream.end':
            break


async def generic_subscribe(receive: callable, debug: dict = None):
    while(True):
        message = await receive()
        if not message.get('exit'):
            recv_data = message.get('data')
            if recv_data is not None:
                if debug:
                    printflush("**%s, %s, RECIEVED, %s, %d" % (time.time_ns(), debug.get('topic'), fnvhash32(recv_data), len(recv_data)))
        else:
            break