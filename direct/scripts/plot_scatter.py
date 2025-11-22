#!/usr/bin/env python3

# import numpy as np
import os
import pandas as pd
import seaborn as sns
from matplotlib import pyplot as plt


if __name__ == '__main__':
    from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter

    parser = ArgumentParser(description='plot differencing results',
                            formatter_class=ArgumentDefaultsHelpFormatter)

    parser.add_argument('csv_file', metavar='FILE',
                        default=None, help='specify result CSV')

    args = parser.parse_args()

    line_flag = True
    kde_flag = False

    # sns.set_theme(style="dark")

    csv_file = args.csv_file

    df = pd.read_csv(csv_file)

    orig_size = len(df)

    # df = df.query('gt_sim > 0 & da_sim > 0')
    # df = df.query('abs(gt_sim - da_sim) > 0.01')

    size = len(df)

    print(f'data size: {size}/{orig_size} ({size/orig_size:.2f})')

    f, ax = plt.subplots(figsize=(6, 6))

    ax.set_xlabel('GumTree Similarity')
    ax.set_ylabel('Diff/AST Similarity')

    if line_flag:
        ax.axline((0, 0), (1, 1), color='black', lw=.5)

    sns.histplot(data=df, x='gt_sim', y='da_sim', ax=ax,
                 bins=128)

    if kde_flag:
        sns.kdeplot(data=df, x='gt_sim', y='da_sim', ax=ax,
                    color='grey', levels=1, linewidths=1)

    _fn, _ = os.path.splitext(os.path.basename(csv_file))
    fn = f'scatter-{_fn}.png'
    f.savefig(fn)
    print(f'saved: {fn}')

    plt.show()
