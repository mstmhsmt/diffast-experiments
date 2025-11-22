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
    'gt_time', 'gt_sim', 'gt_col',
    'da_time', 'da_sim', 'da_col',
    'ok', 'agree'
]


def merge_results():

    for proj in PROJECTS:

        print(f'* {proj}')

        orig_path = f'out.{proj}.csv'
        if not os.path.exists(orig_path):
            orig_path = f'out-sloc.{proj}.csv'

        gt_path = f'out-gumtree.{proj}.csv'
        da_path = f'out-diffast.{proj}.csv'
        out_path = f'out.{proj}.merged.csv'

        if any([not os.path.exists(p) for p in (gt_path, da_path, orig_path)]):
            print('NOT FOUND')
            continue

        gt_tbl = {}

        print(f'reading {gt_path}...')

        with open(gt_path, newline='') as f:
            for row in csv.DictReader(f):

                commit = row['commit']
                path = row['path']
                old = row['old']
                new = row['new']

                gt_time = row['gt_time']
                gt_sim = row['gt_sim']
                gt_col = row['gt_col']

                d = {'gt_time': gt_time, 'gt_sim': gt_sim, 'gt_col': gt_col}

                gt_tbl[(commit, path, old, new)] = d

        da_tbl = {}

        print(f'reading {da_path}...')

        with open(da_path, newline='') as f:
            for row in csv.DictReader(f):

                commit = row['commit']
                path = row['path']
                old = row['old']
                new = row['new']

                da_time = row['da_time']
                da_sim = row['da_sim']
                da_col = row['da_col']

                d = {'da_time': da_time, 'da_sim': da_sim, 'da_col': da_col}

                da_tbl[(commit, path, old, new)] = d

        rows = []

        print(f'reading {orig_path}...')

        with open(orig_path, newline='') as f:
            for row in csv.DictReader(f):

                commit = row['commit']
                path = row['path']
                old = row['old']
                new = row['new']

                key = (commit, path, old, new)

                d = da_tbl[key]
                g = gt_tbl[key]

                row['gt_time'] = g['gt_time']
                row['gt_sim'] = g['gt_sim']
                row['gt_col'] = g['gt_col']

                row['da_time'] = d['da_time']
                row['da_sim'] = d['da_sim']
                row['da_col'] = d['da_col']

                row['ok'] = row['gt_col'] >= row['da_col'] and row['gt_sim'] <= row['da_sim']
                row['agree'] = row['gt_col'] == row['da_col'] and row['gt_sim'] == row['da_sim']

                rows.append(row)

        print(f'{len(rows)} rows merged')

        print(f'dumping into {out_path}...')

        with open(out_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=HEADER)

            writer.writeheader()

            for row in rows:
                writer.writerow(row)


if __name__ == '__main__':
    merge_results()
