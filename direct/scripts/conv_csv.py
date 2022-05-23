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
    'sim', 'col', 'time', 'time_ratio', 'tool'
]


def conv(in_path, out_path):

    rows = []

    print(f'reading {in_path}...')

    with open(in_path, newline='') as f:
        for row in csv.DictReader(f):

            commit = row['commit']
            path = row['path']
            old = row['old']
            new = row['new']
            old_sloc = row['old_sloc']
            new_sloc = row['new_sloc']

            gum_time = float(row['gum_time'])
            gum_sim = float(row['gum_sim'])
            gum_col = int(row['gum_col'])

            dts_time = float(row['dts_time'])
            dts_sim = float(row['dts_sim'])
            dts_col = int(row['dts_col'])

            d = {
                'commit': commit,
                'path': path,
                'old': old,
                'new': new,
                'old_sloc': old_sloc,
                'new_sloc': new_sloc,
            }

            gum_row = d.copy()
            gum_row['tool'] = 'gumtree'
            gum_row['sim'] = gum_sim
            gum_row['col'] = gum_col
            gum_row['time'] = gum_time
            gum_row['time_ratio'] = gum_time / dts_time
            rows.append(gum_row)

            dts_row = d.copy()
            dts_row['tool'] = 'diffast'
            dts_row['sim'] = dts_sim
            dts_row['col'] = dts_col
            dts_row['time'] = dts_time
            dts_row['time_ratio'] = gum_time / dts_time
            rows.append(dts_row)

        nrows = len(rows)

        print(f'dumping {nrows} rows into {out_path}...')

        with open(out_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=HEADER)

            writer.writeheader()

            for row in rows:
                writer.writerow(row)


def conv_all():
    in_path = 'out-merged.csv'
    out_path = 'out-converted.csv'

    conv(in_path, out_path)

    for proj in PROJECTS:
        in_path = f'out-{proj}-merged.csv'
        if os.path.exists(in_path):
            out_path = f'out-{proj}-converted.csv'
            conv(in_path, out_path)


if __name__ == '__main__':
    conv_all()
