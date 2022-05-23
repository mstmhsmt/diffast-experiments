#!/usr/bin/env python3

import os

if __name__ == '__main__':
    c = len(os.sched_getaffinity(0))
    print(c)
