#!/bin/bash

RRJ_CMD=/opt/cca/ddutil/rrj.py

for ru in $(ls samples); do
    for rn in $(ls samples/$ru); do
        cids=""
        for b in $(ls -d samples/$ru/$rn/*-before); do
            before=$(basename $b)
            cids="$cids ${before%-before}"
        done
        echo "*** running RRJ for$cids of samples/$ru/$rn"
        $RRJ_CMD --proj-id $ru/$rn samples/$ru/$rn $cids
    done
done
