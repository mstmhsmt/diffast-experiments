#!/usr/bin/env python3

import os
import csv

PROJECTS = [
    'activemq',
    'commons-io',
    'commons-lang',
    'commons-math',
    'hibernate-orm',
    'hibernate-search',
    'junit4',
    'netty',
    'spring-framework',
    'spring-roo'
]

HEADER = [
    'commit', 'path', 'old', 'old_sloc', 'new', 'new_sloc',
    'gum_time', 'gum_sim', 'gum_col',
    'dts_time', 'dts_sim', 'dts_col',
    'ok', 'agree'
]


def merge_csvs():

    out_path = 'out-merged.csv'

    print(f'dumping into {out_path}...')

    with open(out_path, 'w', newline='') as outf:

        writer = csv.DictWriter(outf, fieldnames=HEADER)

        writer.writeheader()

        for proj in PROJECTS:

            orig_path = f'out-{proj}-merged.csv'

            if not os.path.exists(orig_path):
                orig_path = f'out-{proj}.csv'

            print(f'reading {orig_path}...')

            if not os.path.exists(orig_path):
                print('NOT FOUND')
                continue

            with open(orig_path, newline='') as f:
                for row in csv.DictReader(f):
                    writer.writerow(row)


if __name__ == '__main__':
    merge_csvs()
