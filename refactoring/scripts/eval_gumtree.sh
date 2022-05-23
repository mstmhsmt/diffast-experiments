#!/bin/bash

cd GumTree
gradle clean test --info >& eval_gumtree.log
cd -
grep '\[eval_gumtree\]' GumTree/eval_gumtree.log
