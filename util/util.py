import sys

RANDOM_SIZE = 4
RANDOM_ORDER = "big"
Z_WBITS = -14
Z_END_PATTERN = bytearray(b'\x00\x00\xff\xff')


def printflush(msg):
    print(msg)
    sys.stdout.flush()
