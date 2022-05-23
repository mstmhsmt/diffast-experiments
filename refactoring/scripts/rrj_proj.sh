#!/bin/bash

RRJ_CMD=/opt/cca/ddutil/rrj.py

if [ $# -lt 1 ]; then
    echo "usage: $0 PROJ_ID"
    exit 0
fi

PROJ_ID=$1

cids=""
for b in $(ls -d samples/$PROJ_ID/[0-9a-f]*-before); do
    before=$(basename $b)
    cids="$cids ${before%-before}"
done
echo "*** running RRJ for$cids of samples/$PROJ_ID"
$RRJ_CMD -v --proj-id $PROJ_ID samples/$PROJ_ID $cids
