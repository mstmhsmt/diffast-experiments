#!/bin/bash

scripts/rrj_all_p.sh >& rrj_all_p.log
scripts/eval_rrj.py >& eval_rrj.log
tail -n 15 eval_rrj.log
