# Comparing Diff/AST with GumTree

## Extracting Samples
```
$ tar Jxf samples.txz
```

## Computing Size of Edited Regions
```
$ scripts/shootout.py
```

Processing all samples requires too much time. You can try both on a single project.
```
$ scripts/shootout.py --proj commons-io
```

Consult the help for further details.
```
$ scripts/shootout.py --help
```

### Generating Figures
```
$ scripts/plot_violin_time.py
$ scripts/plot_violin_diff.py
```

## Enumerating Inaccurate Mappings

```
$ scripts/map_eval.py >& map_eval.log
```

The following is taken from DOI:10.5281/zenodo.4281091.
```
DifferentialTesting/expert-results
```
