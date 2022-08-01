# Replication Package for "Diff/AST: A Syntax-Aware Source Code Differencing Tool"

This package contains the following.
* `direct`: For comparing with GumTree directly.
* `refactoring`: For comparing with GumTree through refactoring detection.

Since the archives of the source code samples are quite large, they are managed with [Git LFS](https://git-lfs.github.com/).

The source code of RRJ, an experimental implementation of refactoring detector based in Diff/AST, is available [here](https://github.com/mstmhsmt/rrj).

Note that `direct/GumTreeDiff/gumtree` is added as a submodule. If it is empty, the following command lines will clone it.
```
$ git submodule init
$ git submodule update
```

## Quick start

A docker image is readily available.
```
$ docker pull mhashimoto/diffast-experiments
$ docker run -ti mhashimoto/diffast-experiments /bin/bash
```

See the following to replicate the experiments.
* `direct/README.md`
* `refactoring/README.md`
