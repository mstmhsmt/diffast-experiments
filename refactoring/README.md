# Comparing Diff/AST with GumTree through Refactoring Detection

## Extracting Samples
```
$ tar Jxf samples.txz
```

## Evaluating GumTree
```
$ scripts/eval_gumtree.sh
```

The implementation is based on the following.
```
https://github.com/ameyaKetkar/RMinerEvaluationTools
```

## Evaluating Diff/AST
To implement RRJ (Refactoring Reconstruction for Java), we use an RDF store called Virtuoso, which requires much memory.
We recommend using as many CPU cores as possible and assigning at least 4GB memory for each core.

```
$ scripts/eval_rrj.sh
```
