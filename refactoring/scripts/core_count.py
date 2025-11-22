#!/usr/bin/env python3

import psutil

MAX_COUNT = 128

if __name__ == '__main__':
    _c = psutil.cpu_count(logical=False)
    c = min(_c, MAX_COUNT)
    print(c)
