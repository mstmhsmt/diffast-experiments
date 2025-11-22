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


HEADER = ['commit', 'path', 'old', 'old_sloc', 'new', 'new_sloc',
          'gt_time', 'gt_sim', 'gt_col', 'gt_cost',
          'da_time', 'da_sim', 'da_col', 'da_cost',
          'd_sim', 'd_col', 'd_cost']


if __name__ == '__main__':
    root = 'samples'

    for proj in PROJECTS:
        idx_path = os.path.join(root, proj, 'index.csv')
        gt_path = f'out-gumtree.{proj}.csv'
        da_path = f'out-diffast.{proj}.csv'
        out_path = f'out.{proj}.merged.csv'

        if not os.path.exists(gt_path):
            continue

        if not os.path.exists(da_path):
            continue

        if not os.path.exists(idx_path):
            continue

        print(f'* {proj}')

        idx_tbl = {}

        print(f'reading {idx_path}...')

        with open(idx_path, 'r', newline='') as f:
            for row in csv.DictReader(f):
                commit = row['commit']
                path = row['path']
                old = row['old']
                new = row['new']
                old_sloc = int(row['old_sloc'])
                new_sloc = int(row['new_sloc'])
                d = {'old_sloc': old_sloc, 'new_sloc': new_sloc}
                idx_tbl[(commit, path, old, new)] = d

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
                da_cost = row['da_cost']

                d = {'da_time': da_time, 'da_sim': da_sim, 'da_col': da_col, 'da_cost': da_cost}

                da_tbl[(commit, path, old, new)] = d

        rows = []

        print(f'reading {gt_path}...')

        with open(gt_path, newline='') as f:
            for row in csv.DictReader(f):

                commit = row['commit']
                path = row['path']
                old = row['old']
                new = row['new']

                key = (commit, path, old, new)

                sloc_d = idx_tbl[key]

                d = da_tbl[key]

                row['old_sloc'] = sloc_d['old_sloc']
                row['new_sloc'] = sloc_d['new_sloc']

                row['da_time'] = float(d['da_time'])
                row['da_sim'] = float(d['da_sim'])
                row['da_col'] = int(d['da_col'])
                row['da_cost'] = int(d['da_cost'])

                gt_sim = float(row['gt_sim'])
                gt_col = int(row['gt_col'])
                gt_cost = int(row['gt_cost'])

                row['gt_sim'] = gt_sim
                row['gt_col'] = gt_col
                row['gt_cost'] = gt_cost

                da_sim = row['da_sim']
                da_col = row['da_col']
                da_cost = row['da_cost']

                # row['ok'] = gt_sim <= da_sim
                # row['agree'] = gt_sim == da_sim
                row['d_sim'] = da_sim - gt_sim
                row['d_col'] = gt_col - da_col
                row['d_cost'] = gt_cost - da_cost

                rows.append(row)

        print(f'{len(rows)} rows merged')

        print(f'dumping into {out_path}...')

        with open(out_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=HEADER)

            writer.writeheader()

            for row in rows:
                writer.writerow(row)
