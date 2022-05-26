#!/usr/bin/env python3

# import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib import pyplot as plt


def plot(in_csv, out_file, linear=False):
    df = pd.read_csv(in_csv)

    sns.set_theme(style='ticks', font_scale=1.8)

    f, axs = plt.subplots(1, 2, figsize=(12, 6), sharey=True)
    ax0 = axs[0]
    ax1 = axs[1]

    line_kws = {'linewidth': 1}

    ax0.set_xlabel('Old SLOC')

    if not linear:
        ax0.set_xscale('log')

    sns.histplot(data=df, x='old_sloc', linewidth=0,
                 kde=True, line_kws=line_kws,
                 ax=ax0)
    ax0.lines[0].set_color('k')

    ax1.set_xlabel('New SLOC')

    if not linear:
        ax1.set_xscale('log')

    sns.histplot(data=df, x='new_sloc', linewidth=0,
                 kde=True, line_kws=line_kws,
                 ax=ax1)
    ax1.lines[0].set_color('k')

    f.tight_layout()

    f.savefig(out_file)

    plt.show()


if __name__ == '__main__':
    from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter

    parser = ArgumentParser(description='generate histgram plot for SLOC',
                            formatter_class=ArgumentDefaultsHelpFormatter)

    parser.add_argument('-i', '--input', dest='in_csv', type=str,
                        default='out-merged.csv',
                        help='specify input CSV file')

    parser.add_argument('-o', '--output', dest='out_file', type=str,
                        default='dist_sloc.png',
                        help='specify output file')

    parser.add_argument('--linear', action='store_true',
                        help='use linear scale instead of log scale')

    args = parser.parse_args()

    plot(args.in_csv, args.out_file, linear=args.linear)
