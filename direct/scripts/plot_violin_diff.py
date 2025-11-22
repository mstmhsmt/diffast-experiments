#!/usr/bin/env python3

# import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib import pyplot as plt
from matplotlib.ticker import FormatStrFormatter


def plot(in_csv, out_file, linear=False):

    df = pd.read_csv(in_csv)

    # df = df.query('old_sloc > 1000')

    sns.set_theme(style="ticks", palette="Blues")

    f, ax = plt.subplots(figsize=(8, 8))

    if not linear:
        df = df.query('col > 0')
        ax.set_yscale('log')

    print(f'data size: {len(df)}')

    plt.tick_params(axis='y', which='major', length=8)
    ax.yaxis.set_major_formatter(FormatStrFormatter("%d"))

    sns.violinplot(data=df, x='tool', y='col', inner=None,
                   gridsize=6000,
                   linewidth=0, width=0.95, ax=ax)

    boxprops = {'facecolor': 'none', 'zorder': 3}
    meanprops = {'marker': 'x', 'markeredgecolor': 'black'}

    bp = sns.boxplot(data=df, x='tool', y='col', boxprops=boxprops,
                     fliersize=2, palette='Dark2',
                     showmeans=True,
                     meanprops=meanprops,
                     # showfliers=False,
                     width=0.1, linewidth=1, ax=ax)

    means = df.groupby(['tool'])['col'].mean()
    quantiles = df.groupby(['tool'])['col'].quantile([.0, .25, .5, .75, 1.0])

    _tools = sorted(bp.get_xticklabels(), key=lambda x: x.get_position()[0])
    tools = [t.get_text() for t in _tools]

    fontsize = 'medium'
    fontweight = 'medium'

    for xtick in bp.get_xticks():
        tool = tools[xtick]

        mean = means[tool]
        quantile = quantiles[tool]

        iqr = quantile[.75] - quantile[.25]
        max0 = quantile[.75] + iqr * 1.5
        min0 = max(.0, quantile[.25] - iqr * 1.5)

        print(f'{xtick} {tool}: mean={mean} iqr={iqr} min0={min0} max0={max0}')
        print(quantile)

        bp.text(xtick - .24, mean, 'Mean={:.2f}'.format(mean),
                horizontalalignment='center', verticalalignment='center',
                size=fontsize, color='black', weight=fontweight)

        for q in quantile:
            bp.text(xtick + .16, q, '{:.2f}'.format(q),
                    horizontalalignment='center', verticalalignment='center',
                    size=fontsize, color='black', weight=fontweight)

        bp.text(xtick + .16, min0, '{:.2f}'.format(min0),
                horizontalalignment='center', verticalalignment='center',
                size=fontsize, color='black', weight=fontweight)

        bp.text(xtick + .16, max0, '{:.2f}'.format(max0),
                horizontalalignment='center', verticalalignment='center',
                size=fontsize, color='black', weight=fontweight)

    tool_tbl = {'diffast': 'Diff/AST', 'gumtree': 'GumTree'}

    fontdict = {'fontsize': 'large'}
    bp.set_xticklabels([tool_tbl[t] for t in tools], fontdict=fontdict)

    ax.set_xlabel(None)

    ax.set_ylabel('Difference (edited text region size)', fontdict=fontdict)

    # f.tight_layout()

    f.savefig(out_file)

    plt.show()


if __name__ == '__main__':
    from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter

    parser = ArgumentParser(description='generate violin plot for edited text region size',
                            formatter_class=ArgumentDefaultsHelpFormatter)

    parser.add_argument('-i', '--input', dest='in_csv', type=str,
                        default='out.converted.csv',
                        help='specify input CSV file')

    parser.add_argument('-o', '--output', dest='out_file', type=str,
                        default='violin_diff.png',
                        help='specify output file')

    parser.add_argument('--linear', action='store_true',
                        help='use linear scale instead of log scale')

    args = parser.parse_args()

    plot(args.in_csv, args.out_file, linear=args.linear)
