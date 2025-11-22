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
    'commit', 'path',
    'old', 'old_sloc',
    'new', 'new_sloc',
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

            try:
                gt_time = float(row['gt_time'])
                gt_sim = float(row['gt_sim'])
                gt_col = int(row['gt_col'])

                da_time = float(row['da_time'])
                da_sim = float(row['da_sim'])
                da_col = int(row['da_col'])
            except Exception:
                print(f'! {commit} {path}')
                raise

            d = {
                'commit': commit,
                'path': path,
                'old': old,
                'new': new,
                'old_sloc': old_sloc,
                'new_sloc': new_sloc,
            }

            gt_row = d.copy()
            gt_row['tool'] = 'gumtree'
            gt_row['sim'] = gt_sim
            gt_row['col'] = gt_col
            gt_row['time'] = gt_time
            gt_row['time_ratio'] = gt_time / da_time
            rows.append(gt_row)

            da_row = d.copy()
            da_row['tool'] = 'diffast'
            da_row['sim'] = da_sim
            da_row['col'] = da_col
            da_row['time'] = da_time
            da_row['time_ratio'] = gt_time / da_time
            rows.append(da_row)

        nrows = len(rows)

        print(f'dumping {nrows} rows into {out_path}...')

        with open(out_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=HEADER)

            writer.writeheader()

            for row in rows:
                writer.writerow(row)


def conv_all():
    in_path = 'out.merged.csv'
    out_path = 'out.converted.csv'

    conv(in_path, out_path)

    for proj in PROJECTS:
        in_path = f'out.{proj}.merged.csv'
        if os.path.exists(in_path):
            out_path = f'out.{proj}.converted.csv'
            conv(in_path, out_path)


if __name__ == '__main__':
    conv_all()
