#!/bin/bash

RRJ_CMD=/opt/cca/ddutil/rrj.py

HERE=$(dirname $0)

NPROCS=$($HERE/core_count.py)
PORT=1111

count=0

for r in $(ls -d -S samples/*/*); do
    repo=${r#samples/}
    cids=""
    for b in $(ls -d samples/$repo/[0-9a-f]*-before); do
        before=$(basename $b)
        cids="$cids ${before%-before}"
    done
    port=$(expr $PORT + $count)
    sem -j $NPROCS "$RRJ_CMD -v --port $port --proj-id $repo samples/$repo $cids; echo done: [$count] $repo$cids"
    echo "[$count] $repo"
    count=$(expr $count + 1)
done
sleep 3
sem --wait
