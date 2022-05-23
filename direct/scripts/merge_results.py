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


def merge_results():

    for proj in PROJECTS:

        print(f'* {proj}')

        orig_path = f'out-{proj}.csv'
        if not os.path.exists(orig_path):
            orig_path = f'out-sloc-{proj}.csv'

        gt_path = f'out-gumtree-{proj}.csv'
        da_path = f'out-diffast-{proj}.csv'
        out_path = f'out-{proj}-merged.csv'

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

                gum_time = row['gum_time']
                gum_sim = row['gum_sim']
                gum_col = row['gum_col']

                d = {'gum_time': gum_time, 'gum_sim': gum_sim, 'gum_col': gum_col}

                gt_tbl[(commit, path, old, new)] = d

        da_tbl = {}

        print(f'reading {da_path}...')

        with open(da_path, newline='') as f:
            for row in csv.DictReader(f):

                commit = row['commit']
                path = row['path']
                old = row['old']
                new = row['new']

                dts_time = row['dts_time']
                dts_sim = row['dts_sim']
                dts_col = row['dts_col']

                d = {'dts_time': dts_time, 'dts_sim': dts_sim, 'dts_col': dts_col}

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

                row['gum_time'] = g['gum_time']
                row['gum_sim'] = g['gum_sim']
                row['gum_col'] = g['gum_col']

                row['dts_time'] = d['dts_time']
                row['dts_sim'] = d['dts_sim']
                row['dts_col'] = d['dts_col']

                row['ok'] = row['gum_col'] >= row['dts_col'] and row['gum_sim'] <= row['dts_sim']
                row['agree'] = row['gum_col'] == row['dts_col'] and row['gum_sim'] == row['dts_sim']

                rows.append(row)

        print('{} rows merged'.format(len(rows)))

        print(f'dumping into {out_path}...')

        with open(out_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=HEADER)

            writer.writeheader()

            for row in rows:
                writer.writerow(row)


if __name__ == '__main__':
    merge_results()
