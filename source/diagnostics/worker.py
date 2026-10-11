import sys
from core import record, release

if __name__ == '__main__' and len(sys.argv) == 2:
    try:
        record(sys.argv[1])
    finally:
        release(sys.argv[1])
