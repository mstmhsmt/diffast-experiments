#!/usr/bin/env python3

import pandas as pd
import seaborn as sns
from matplotlib import pyplot as plt


def plot(in_csv, out_file):
    df = pd.read_csv(in_csv)

    f, ax = plt.subplots(figsize=(6, 6))

    ax.set_xlabel('GumTree Similarity')
    ax.set_ylabel('Diff/AST Similarity')

    sns.histplot(data=df, x='gum_sim', y='dts_sim', ax=ax)

    sns.kdeplot(data=df, x='gum_sim', y='dts_sim', ax=ax,
                color='black', linewidths=.3)

    f.savefig(out_file)

    plt.show()


if __name__ == '__main__':
    from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter

    parser = ArgumentParser(description='generate bivariate scatter plot for computed similarity',
                            formatter_class=ArgumentDefaultsHelpFormatter)

    parser.add_argument('-i', '--input', dest='in_csv', type=str,
                        default='out-merged.csv',
                        help='specify input CSV file')

    parser.add_argument('-o', '--output', dest='out_file', type=str,
                        default='scatter.png',
                        help='specify output file')

    args = parser.parse_args()

    plot(args.in_csv, args.out_file)
