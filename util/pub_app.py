import asyncio, os, time, sys
from fnvhash import fnv1a_32 as fnvhash32
sys.path.append("../util/") # absolute path to util's folder
from util import printflush, RANDOM_SIZE, RANDOM_ORDER


class Data_Fixed_Generator:
    def __init__(self):
        self.counter = -1
        self.id = int.from_bytes(os.urandom(RANDOM_SIZE), RANDOM_ORDER)

    async def __call__(self):
        self.counter += 1
        self.id += 1
        return "PUBLISHER_FIXED_DATA_%06d_%010d" % (self.counter, self.id)


def create_data_generator(class_generator: callable) -> None:
    if class_generator is None:
        data_generator = Data_Fixed_Generator()
    else:
        data_generator = class_generator()
    return data_generator


async def webtransport_publish(send: callable, close_event: asyncio.Event, class_generator: callable = None, debug: dict = {}) -> None:
    data_generator = create_data_generator(class_generator)
    if close_event.is_set():
        return
    while(True):
        try:
            start_time = time.time()
            send_data = (await data_generator()).encode('utf-8')
            if debug:
                printflush("**%s, %s, PUBLISHING, %s, %d" % (time.time_ns(), debug.get('topic'), fnvhash32(send_data), len(send_data)))
            await send({
                    "data": send_data,
                    "type": "webtransport.stream.send",
                })
            await asyncio.wait_for(close_event.wait(), 1-(time.time()-start_time))
            await data_generator.terminate()
            return
        except:
            pass


async def generic_publish(send: callable, close_event: asyncio.Event, class_generator: callable = None, debug: dict = None) -> None:
    data_generator = create_data_generator(class_generator)
    if close_event.is_set():
        return
    while(True):
        try:
            start_time = time.time()
            send_data = (await data_generator()).encode('utf-8')
            if debug:
                printflush("**%s, %s, PUBLISHING, %s, %d" % (time.time_ns(), debug.get('topic'), fnvhash32(send_data), len(send_data)))
            await send(send_data)   
            await asyncio.wait_for(close_event.wait(), 1-(time.time()-start_time))
            await data_generator.terminate()
            return
        except:
            pass