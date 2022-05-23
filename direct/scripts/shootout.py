#!/usr/bin/env python3

import sys
import os
import re
# import json
import simplejson as json
from subprocess import run
import csv
import time
import multiprocessing as mp
import math
import logging

import sloccount
from merge_results import merge_results
from merge_csvs import merge_csvs
from conv_csv import conv_all

logger = mp.get_logger()

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
    'spring-roo',
]

GUMTREE_DIR = '/root/direct/GumTreeDiff'
GUMTREE_CMD = os.path.join(GUMTREE_DIR, 'run.sh')

SIMAST_CMD = '/opt/cca/bin/simast.opt'

EXCLUDED_TYPES = ('Javadoc', 'TagElement', 'TextElement', 'comment')

MAX_NRETRIES = 3

SLOCCOUNT_CACHE_NAME = 'CACHE-sloccount'

try:
    NPROCS = len(os.sched_getaffinity(0))
except Exception:
    NPROCS = os.cpu_count()


def get_time():
    return time.monotonic()


def load_json(path):
    d = None
    with open(path) as f:
        d = json.load(f)
    return d


def check_tree(tree, ty_st_ed):
    ty, st, ed = ty_st_ed
    res = False
    x = tree['type']
    lab = tree.get('label', None)
    if lab is not None:
        x += ': '+lab
    if x == ty:
        pos = int(tree['pos'])
        if pos == st:
            sz = int(tree['length'])
            if ed <= pos + sz:
                res = True
    return res


def find_subtree(tree, ty_st_ed):
    if check_tree(tree, ty_st_ed):
        return tree

    for c in tree['children']:
        r = find_subtree(c, ty_st_ed)
        if r is not None:
            return r

    return None


def count_nodes(nd):
    count = 1

    if nd['type'] in EXCLUDED_TYPES:
        return 0

    for c in nd['children']:
        count += count_nodes(c)

    return count


def count_tree_nodes(tree):
    root = tree['root']
    c = count_nodes(root)
    return c


PAT = re.compile(r'^(?P<type>.*)\[(?P<start>[0-9]+),(?P<end>[0-9]+)\]$')


def get_info(lab):
    res = None

    if any([lab.startswith(t) for t in EXCLUDED_TYPES]):
        return res

    m = PAT.match(lab)
    if m:
        ty = m.group('type').rstrip()
        st = int(m.group('start'))
        ed = int(m.group('end'))
        res = (ty, st, ed)
    return res


def get_node_region(nd):
    r = set()
    st = int(nd['pos'])
    ed = st + int(nd['length'])
    r = set(range(st, ed))
    for c in nd['children']:
        r.update(get_node_region(c))
    return r


def get_tree_region(tree):
    root = tree['root']
    r = get_node_region(root)
    return r


def get_region(lab):
    r = None
    if any([lab.startswith(t) for t in EXCLUDED_TYPES]):
        return r
    m = PAT.match(lab)
    if m:
        st = int(m.group('start'))
        ed = int(m.group('end'))
        r = set(range(st, ed))
    return r


def get_matches(diff):
    matches = set()
    for m in diff['matches']:
        if any([m['src'].startswith(t) or m['dest'].startswith(t)
                for t in EXCLUDED_TYPES]):
            logger.debug(f'excluded: {m}')
        else:
            info = get_info(m['src'])
            matches.add(info)
    return matches


def get_nodes(subtree):
    infos = set()

    if subtree['type'] in EXCLUDED_TYPES:
        return infos
    else:
        st = int(subtree['pos'])
        ed = st + int(subtree['length'])
        ty = subtree['type']
        lab = subtree.get('label', None)
        if lab is not None:
            ty += ': '+lab
        info = (ty, st, ed)
        infos.add(info)

    for c in subtree['children']:
        infos.update(get_nodes(c))

    return infos


def similarity(src_tree, dst_tree, diff):
    src_sz = count_tree_nodes(src_tree)
    dst_sz = count_tree_nodes(dst_tree)

    matches = get_matches(diff)

    logger.debug('src_sz={} dst_sz={} nmatches={}'
                 .format(src_sz, dst_sz, len(matches)))

    moved_nodes = set()
    updated_nodes = set()
    deleted_nodes = set()

    for a in diff['actions']:
        act = a['action']
        if act == 'update-node':
            info = get_info(a['tree'])
            if info is not None:
                updated_nodes.add(info)

        elif act == 'delete-node':
            info = get_info(a['tree'])
            if info is not None:
                deleted_nodes.add(info)

        elif act == 'delete-tree':
            info = get_info(a['tree'])
            if info is not None:
                subtree = find_subtree(src_tree['root'], info)
                if subtree is not None:
                    deleted_nodes.update(get_nodes(subtree))
                else:
                    logger.debug('not found: {} {} {}'.format(*info))

        elif act == 'move-tree':
            info = get_info(a['tree'])
            if info is not None:
                subtree = find_subtree(src_tree['root'], info)
                if subtree is not None:
                    moved_nodes.update(get_nodes(subtree))
                else:
                    logger.debug('not found: {} {} {}'.format(*info))

    matches.difference_update(moved_nodes | updated_nodes | deleted_nodes)
    nmatches = len(matches)

    sim = 2.0 * nmatches / (src_sz + dst_sz)

    return sim


def delta(src_tree, dst_tree, diff):
    matches = get_matches(diff)
    cost = 0
    nrelabels = 0
    for a in diff['actions']:
        act = a['action']
        if act == 'update-node':
            info = get_info(a['tree'])
            if info is not None:
                cost += 1
                nrelabels += 1

        elif act == 'delete-node':
            info = get_info(a['tree'])
            if info is not None:
                cost += 1

        elif act == 'delete-tree':
            info = get_info(a['tree'])
            if info is not None:
                subtree = find_subtree(src_tree['root'], info)
                if subtree is not None:
                    cost += len(get_nodes(subtree))
                else:
                    logger.debug('not found: {} {} {}'.format(*info))

        elif act == 'insert-node':
            info = get_info(a['tree'])
            if info is not None:
                cost += 1

        elif act == 'insert-tree':
            info = get_info(a['tree'])
            if info is not None:
                subtree = find_subtree(src_tree['root'], info)
                if subtree is not None:
                    cost += len(get_nodes(subtree))
                else:
                    logger.debug('not found: {} {} {}'.format(*info))

        elif act == 'move-tree':
            info = get_info(a['tree'])
            if info is not None:
                cost += 1

    nmatches = len(matches)
    logger.debug(f'cost={cost} nmatches={nmatches}')

    r = {'cost': cost, 'nmappings': nmatches, 'nrelabels': nrelabels}

    return r


def get_reg(lab):
    r = None
    m = PAT.match(lab)
    if m:
        st = int(m.group('start'))
        ed = int(m.group('end'))
        r = (st, ed)
    else:
        logger.warning(f'failed to get region: lab={lab}')
    return r


def get_region_mapping(diff):
    tbl = {}
    for x in diff['matches']:
        src = get_reg(x['src'])
        dst = get_reg(x['dest'])
        if src and dst:
            tbl[src] = dst
    return tbl


def get_mapped_region(lab, mapping):
    src_reg = get_reg(lab)
    dst_reg = mapping[src_reg]
    # logger.debug(f'{src_reg} --> {dst_reg}')
    r = set(range(*dst_reg))
    return r


def text_similarity(src_tree, dst_tree, diff,
                    align0, align1,
                    src_region_sz=None, dst_region_sz=None):

    if src_region_sz is None:
        # src_region = get_tree_region(src_tree)
        # src_region_sz = len(src_region)
        src_region_sz = len(align0)

    if dst_region_sz is None:
        # dst_region = get_tree_region(dst_tree)
        # dst_region_sz = len(dst_region)
        dst_region_sz = len(align1)

    src_colored_region = set()
    dst_colored_region = set()

    mapping = get_region_mapping(diff)

    for a in diff['actions']:
        act = a['action']
        lab = a['tree']
        if act == 'update-node':
            r = get_region(lab)
            if r is not None:
                src_colored_region.update(r)
                dst_colored_region.update(get_mapped_region(lab, mapping))

        elif act == 'delete-node':
            r = get_region(lab)
            if r is not None:
                src_colored_region.update(r)

        elif act == 'delete-tree':
            r = get_region(lab)
            if r is not None:
                src_colored_region.update(r)

        elif act == 'insert-node':
            r = get_region(lab)
            if r is not None:
                dst_colored_region.update(r)

        elif act == 'insert-tree':
            r = get_region(lab)
            if r is not None:
                dst_colored_region.update(r)

        elif act == 'move-tree':
            r = get_region(lab)
            if r is not None:
                src_colored_region.update(r)
                dst_colored_region.update(get_mapped_region(lab, mapping))

    src_colored_region &= align0
    dst_colored_region &= align1

    src_colored_region_sz = len(src_colored_region)
    dst_colored_region_sz = len(dst_colored_region)

    colored = src_colored_region_sz + dst_colored_region_sz
    region_sz = src_region_sz + dst_region_sz

    m = region_sz - colored

    sim = m / region_sz

    logger.debug(f'file:{src_region_sz}->{dst_region_sz}'
                 f', colored:{src_colored_region_sz}->{dst_colored_region_sz}'
                 f', sim={sim}')

    d = {'similarity': sim, 'colored': colored}

    return d


def gumtree_diff(path0, path1):
    cmd = f'{GUMTREE_CMD} textdiff -f json {path0} {path1}'
    diff = None
    s = None
    try:
        p = run(cmd, shell=True, capture_output=True)
        s = p.stdout
        diff = json.loads(s)
    except Exception as e:
        logger.error(f'{path0} {path1}: {e}: {s}')
    return diff


def gumtree_parse(path):
    cmd = f'{GUMTREE_CMD} parse -f json {path}'
    tree = None
    try:
        p = run(cmd, shell=True, capture_output=True)
        tree = json.loads(p.stdout)
    except Exception as e:
        logger.error(f'{path}: {e}')
    return tree


def gumtree_node_count(path):
    c = None
    t = gumtree_parse(path)
    if t is not None:
        c = count_tree_nodes(t)
    return c


def gumtree_sim(path0, path1):
    t0 = gumtree_parse(path0)
    t1 = gumtree_parse(path1)
    d = gumtree_diff(path0, path1)
    sim = similarity(t0, t1, d)
    return round(sim, 6)


def gumtree_dist(path0, path1):
    t0 = gumtree_parse(path0)
    t1 = gumtree_parse(path1)
    d = gumtree_diff(path0, path1)
    r = delta(t0, t1, d)
    dist = r['cost'] / r['nmappings']
    return dist


def gumtree_delta(path0, path1):
    r = None
    t0 = gumtree_parse(path0)
    if t0 is not None:
        t1 = gumtree_parse(path1)
        if t1 is not None:
            d = gumtree_diff(path0, path1)
            if d is not None:
                r = delta(t0, t1, d)
    return r


def text_gumtree_sim(path0, path1):
    t0 = gumtree_parse(path0)
    t1 = gumtree_parse(path1)
    d = gumtree_diff(path0, path1)
    try:
        align0 = get_token_regions(path0)
        align1 = get_token_regions(path1)
        r = text_similarity(t0, t1, d, align0, align1)
        sim = r['similarity']
        col = r['colored']
    except Exception as e:
        logger.error(f'{path0} {path1}: {e}')
        raise
    logger.debug(f'sim={sim} col={col}')
    return {'similarity': round(sim, 6), 'colored': col}


def diffast_sim(path0, path1):
    cmd = f'{SIMAST_CMD} -clearcache {path0} {path1}'
    p = run(cmd, shell=True, capture_output=True)
    sim = float(p.stdout)
    return sim


def get_seg_region0(h):
    r = set()
    try:
        for seg in h['segments1']:
            st = seg['start']
            ed = seg['end']
            r.update(set(range(st, ed+1)))
    except KeyError:
        pass
        # st = h['start1']
        # ed = h['end1']
        # r.update(set(range(st, ed+1)))
    return r


def get_seg_region1(h):
    r = set()
    try:
        for seg in h['segments2']:
            st = seg['start']
            ed = seg['end']
            r.update(set(range(st, ed+1)))
    except KeyError:
        pass
        # st = h['start2']
        # ed = h['end2']
        # r.update(set(range(st, ed+1)))
    return r


def is_ws(c):
    return c in (' ', '\t', '\r', '\n')


def show_regions(r):
    li = sorted(list(r))
    head = True
    end = False
    for i, x in enumerate(li):
        try:
            next = li[i+1]
        except IndexError:
            end = True

        if head:
            sys.stdout.write(f'{x}')
            head = False
        elif not end and next == x + 1:
            head = False
        else:
            sys.stdout.write(f'-{x}\n')
            head = True


def get_token_regions(path):
    r = set()
    comment_head_flag = False
    block_comment_flag = False
    block_comment_end_head_flag = False
    line_comment_flag = False
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        for i, c in enumerate(f.read()):
            if comment_head_flag:
                if c == '/':
                    line_comment_flag = True
                elif c == '*':
                    block_comment_flag = True
                else:
                    r.add(i - 1)
                    r.add(i)

                comment_head_flag = False

            elif block_comment_flag:
                if block_comment_end_head_flag:
                    if c == '/':
                        block_comment_flag = False
                    elif c == '*':
                        pass
                    else:
                        block_comment_end_head_flag = False

                elif c == '*':
                    block_comment_end_head_flag = True

            elif line_comment_flag:
                if c in ('\n', '\r'):
                    line_comment_flag = False

            elif c == '/':
                comment_head_flag = True

            elif is_ws(c):
                pass
            else:
                r.add(i)

    return r


def read_diff_json(diff_json, align0, align1):
    with open(diff_json, 'r') as f:
        d = []
        try:
            d = json.load(f)
        except Exception as e:
            logger.error(f'invalid JSON file: {diff_json}: {e}')
        r0 = set()
        r1 = set()
        for h in d:
            if h is not None:
                tag = h['tag']
                if tag == 'DELETE':
                    r0.update(get_seg_region0(h))
                if tag == 'INSERT':
                    r1.update(get_seg_region1(h))
                elif tag == 'MOVE' or tag == 'MOVREL':
                    r0.update(get_seg_region0(h))
                    r1.update(get_seg_region1(h))
                elif tag == 'RELABEL':
                    r0.update(get_seg_region0(h))
                    r1.update(get_seg_region1(h))

        r0 &= align0
        r1 &= align1

        csz0 = len(r0)
        csz1 = len(r1)

        return (csz0, csz1)


def text_diffast_sim(path0, path1, keep_going=False, scan_huge_arrays=False,
                     use_cache=True, cache_dir=None):

    worker_id = mp.current_process().name

    opt = ''
    if keep_going:
        opt += ' -k'
    if scan_huge_arrays:
        opt += ' -scan-huge-arrays'
    if not use_cache:
        opt += ' -clearcache'
    if cache_dir is not None:
        opt += f' -cache {cache_dir}'

    opt += f' -localcachename {worker_id}'

    cmd = f'{SIMAST_CMD}{opt} {path0} {path1}'
    p = run(cmd, shell=True, capture_output=True)

    if str(p.stdout).strip() == '1.0':
        return {'similarity': 1.0, 'colored': 0}

    cmd = f'{SIMAST_CMD} -getcache -localcachename {worker_id} {path0} {path1}'
    p = run(cmd, shell=True, capture_output=True, text=True)

    cache_dir = p.stdout.strip()
    diff_json = os.path.join(cache_dir, 'diff.json')

    if not os.path.exists(diff_json):
        stat_path = os.path.join(cache_dir, 'stat')
        if not os.path.exists(stat_path):
            logger.warning(f'not found: {stat_path}')
            logger.warning(f'failed to compare: {path0} {path1}')
            return {'similarity': 0.0, 'colored': math.nan}
        with open(stat_path) as f:
            for _line in f:
                line = _line.strip()
                if line == 'total changes : 0':
                    return {'similarity': 1.0, 'colored': 0}
    sz0 = 0
    sz1 = 0
    csz0 = 0
    csz1 = 0
    sim = 0
    colored = 0
    nretries = 0
    while nretries <= MAX_NRETRIES:
        try:
            if nretries > 0:
                logger.warning(f'retrying to read {diff_json}...')

            align0 = get_token_regions(path0)
            align1 = get_token_regions(path1)
            sz0 = len(align0)
            sz1 = len(align1)
            csz0, csz1 = read_diff_json(diff_json, align0, align1)
            sz = sz0 + sz1
            colored = csz0 + csz1
            m = sz - colored
            sim = m / sz
            break
        except Exception as e:
            nretries += 1
            if nretries > MAX_NRETRIES:
                logger.error(f'failed to read diff.json: {e}')
            else:
                time.sleep(2**nretries)

    logger.debug(f'file:{sz0}->{sz1}, colored:{csz0}->{csz1}, sim={sim}')

    return {'similarity': round(sim, 6), 'colored': colored}


def gt_main():
    from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
    parser = ArgumentParser(description='GumTreeSim',
                            formatter_class=ArgumentDefaultsHelpFormatter)
    parser.add_argument('original', type=str, metavar='ORIGINAL',
                        help='original source file')
    parser.add_argument('modified', type=str, metavar='MODIFIED',
                        help='modified source file')
    args = parser.parse_args()
    # sim = gumtree_sim(args.original, args.modified)
    sim = text_gumtree_sim(args.original, args.modified)
    print(sim)


def sloccount_proj(root, proj):
    logger.info(f'proj="{proj}"')
    print(f'proj="{proj}"')

    outfile = os.path.join(f'out-sloc-{proj}.csv')

    with open(outfile, 'w', newline='') as outf:
        header = ['commit', 'path', 'old', 'old_sloc', 'new', 'new_sloc']

        writer = csv.DictWriter(outf, fieldnames=header)
        writer.writeheader()

        d = os.path.join(root, proj)
        d0 = os.path.join(d, '0')
        d1 = os.path.join(d, '1')

        with open(os.path.join(d, 'index.csv'), newline='') as idxf:
            for ex in csv.DictReader(idxf):
                commit = ex['commit']
                path = ex['path']
                fn0 = ex['old']
                fn1 = ex['new']

                path0 = os.path.join(d0, fn0)
                path1 = os.path.join(d1, fn1)

                old_sloc = sloccount.sloccount_for_lang('java', path0)
                new_sloc = sloccount.sloccount_for_lang('java', path1)

                row = {'commit': commit, 'path': path,
                       'old': fn0, 'old_sloc': old_sloc,
                       'new': fn1, 'new_sloc': new_sloc}

                writer.writerow(row)

        logger.info(f'results dumped into {outfile}')


def get_tasks(root, proj, use_cache=False):

    tasks = []

    d = os.path.join(root, proj)
    d0 = os.path.join(d, '0')
    d1 = os.path.join(d, '1')

    with open(os.path.join(d, 'index.csv'), newline='') as idxf:
        for ex in csv.DictReader(idxf):
            commit = ex['commit']
            path = ex['path']
            fn0 = ex['old']
            fn1 = ex['new']
            logger.info(f'{fn0}')
            logger.info(f' --> {fn1}')
            path0 = os.path.join(d0, fn0)
            path1 = os.path.join(d1, fn1)

            task = {'commit': commit, 'path': path, 'old': fn0, 'new': fn1,
                    'path0': path0, 'path1': path1}

            if use_cache:
                task['use_cache'] = True

            tasks.append(task)

    return tasks


def sloccount_wrapper(task):
    path0 = task['path0']
    path1 = task['path1']
    pid = os.getpid()
    datadir0 = os.path.join(SLOCCOUNT_CACHE_NAME, f'{pid}-0')
    datadir1 = os.path.join(SLOCCOUNT_CACHE_NAME, f'{pid}-1')
    sloc0 = sloccount.sloccount_for_lang('java', path0, datadir=datadir0)
    sloc1 = sloccount.sloccount_for_lang('java', path1, datadir=datadir1)
    row = dict(task)
    del row['path0']
    del row['path1']
    row['old_sloc'] = sloc0
    row['new_sloc'] = sloc1
    return row


def sloccount_proj_mp(root, proj, nprocs=1):
    logger.info(f'proj="{proj}" nprocs={nprocs}')
    print(f'proj="{proj}" nprocs={nprocs}')

    if not os.path.exists(SLOCCOUNT_CACHE_NAME):
        os.makedirs(SLOCCOUNT_CACHE_NAME)

    tasks = get_tasks(root, proj)
    ntasks = len(tasks)

    print(f'{ntasks} tasks found')

    rows = []

    with mp.Pool(nprocs) as pool:
        for row in pool.imap(sloccount_wrapper, tasks, 4):
            rows.append(row)
            nrows = len(rows)
            sys.stdout.write(' {:2.2f}%\r'.format(nrows*100/ntasks))

    outfile = os.path.join(f'out-sloc-{proj}.csv')
    print(f'dumping into {outfile}...')
    with open(outfile, 'w', newline='') as outf:

        header = ['commit', 'path', 'old', 'old_sloc', 'new', 'new_sloc']

        writer = csv.DictWriter(outf, fieldnames=header)
        writer.writeheader()

        for row in rows:
            writer.writerow(row)

        logger.info(f'results dumped into {outfile}')


def shootout1(root, proj):
    logger.info(f'proj="{proj}"')
    print(f'proj="{proj}"')

    outfile = os.path.join(f'out-{proj}.csv')

    with open(outfile, 'w', newline='') as outf:

        header = ['commit', 'path', 'old', 'old_sloc', 'new', 'new_sloc',
                  'gum_time', 'gum_sim',
                  'dts_time', 'dts_sim',
                  'ok', 'agree']
        writer = csv.DictWriter(outf, fieldnames=header)
        writer.writeheader()

        d = os.path.join(root, proj)
        d0 = os.path.join(d, '0')
        d1 = os.path.join(d, '1')

        with open(os.path.join(d, 'index.csv'), newline='') as idxf:
            for ex in csv.DictReader(idxf):
                commit = ex['commit']
                path = ex['path']
                fn0 = ex['old']
                fn1 = ex['new']
                logger.info(f'{fn0}')
                logger.info(f' --> {fn1}')
                path0 = os.path.join(d0, fn0)
                path1 = os.path.join(d1, fn1)

                old_sloc = sloccount.sloccount_for_lang('java', path0)
                new_sloc = sloccount.sloccount_for_lang('java', path1)

                st_time = get_time()
                r = text_gumtree_sim(path0, path1)
                gum_sim = r['similarity']
                gum_col = r['colored']
                gum_time = get_time() - st_time
                logger.info(f'gum_time={gum_time}')

                st_time = get_time()
                r = text_diffast_sim(path0, path1, keep_going=True,
                                     scan_huge_arrays=True)
                dts_sim = r['similarity']
                dts_col = r['colored']
                dts_time = get_time() - st_time
                logger.info(f'dts_time={dts_time}')

                ok = gum_sim <= dts_sim and gum_col >= dts_col
                agree = gum_sim == dts_sim and gum_col == dts_col
                row = {'commit': commit, 'path': path,
                       'old': fn0, 'old_sloc': old_sloc,
                       'new': fn1, 'new_sloc': new_sloc,
                       'gum_time': gum_time, 'gum_sim': gum_sim, 'gum_col': gum_col,
                       'dts_time': dts_time, 'dts_sim': dts_sim, 'dts_col': dts_col,
                       'ok': ok, 'agree': agree}
                writer.writerow(row)

        logger.info(f'results dumped into {outfile}')


def gt_proj(root, proj):
    logger.info(f'proj="{proj}"')
    print(f'proj="{proj}"')

    outfile = os.path.join(f'out-gumtree-{proj}.csv')

    with open(outfile, 'w', newline='') as outf:

        header = ['commit', 'path', 'old', 'new',
                  'gum_time', 'gum_sim', 'gum_col']

        writer = csv.DictWriter(outf, fieldnames=header)
        writer.writeheader()

        d = os.path.join(root, proj)
        d0 = os.path.join(d, '0')
        d1 = os.path.join(d, '1')

        with open(os.path.join(d, 'index.csv'), newline='') as idxf:
            for ex in csv.DictReader(idxf):
                commit = ex['commit']
                path = ex['path']
                fn0 = ex['old']
                fn1 = ex['new']
                logger.info(f'{fn0}')
                logger.info(f' --> {fn1}')
                path0 = os.path.join(d0, fn0)
                path1 = os.path.join(d1, fn1)

                st_time = get_time()
                r = text_gumtree_sim(path0, path1)
                gum_sim = r['similarity']
                gum_col = r['colored']
                gum_time = get_time() - st_time
                logger.info(f'gum_time={gum_time}')

                row = {'commit': commit, 'path': path,
                       'old': fn0, 'new': fn1,
                       'gum_time': gum_time, 'gum_sim': gum_sim, 'gum_col': gum_col,
                       }

                writer.writerow(row)

        logger.info(f'results dumped into {outfile}')


def diffast_proj(root, proj, use_cache=True):
    logger.info(f'proj="{proj}"')
    print(f'proj="{proj}"')

    outfile = os.path.join(f'out-diffast-{proj}.csv')

    with open(outfile, 'w', newline='') as outf:

        header = ['commit', 'path', 'old', 'new',
                  'dts_time', 'dts_sim', 'dts_col']

        writer = csv.DictWriter(outf, fieldnames=header)
        writer.writeheader()

        d = os.path.join(root, proj)
        d0 = os.path.join(d, '0')
        d1 = os.path.join(d, '1')

        with open(os.path.join(d, 'index.csv'), newline='') as idxf:
            for ex in csv.DictReader(idxf):
                commit = ex['commit']
                path = ex['path']
                fn0 = ex['old']
                fn1 = ex['new']
                logger.info(f'{fn0}')
                logger.info(f' --> {fn1}')
                path0 = os.path.join(d0, fn0)
                path1 = os.path.join(d1, fn1)

                st_time = get_time()
                r = text_diffast_sim(path0, path1, keep_going=True,
                                     scan_huge_arrays=True,
                                     use_cache=use_cache)
                dts_sim = r['similarity']
                dts_col = r['colored']
                dts_time = get_time() - st_time
                logger.info(f'dts_time={dts_time}')

                row = {'commit': commit, 'path': path,
                       'old': fn0, 'new': fn1,
                       'dts_time': dts_time, 'dts_sim': dts_sim, 'dts_col': dts_col,
                       }

                writer.writerow(row)

        logger.info(f'results dumped into {outfile}')


def simast_wrapper(task):
    path0 = task['path0']
    path1 = task['path1']
    use_cache = task.get('use_cache', False)
    st_time = get_time()
    r = text_diffast_sim(path0, path1, keep_going=True,
                         scan_huge_arrays=True, use_cache=use_cache)
    dts_sim = r['similarity']
    dts_col = r['colored']
    dts_time = get_time() - st_time
    row = dict(task)
    del row['path0']
    del row['path1']
    row['dts_time'] = dts_time
    row['dts_sim'] = dts_sim
    row['dts_col'] = dts_col
    try:
        del row['use_cache']
    except Exception:
        pass
    return row


def diffast_proj_mp(root, proj, use_cache=False, nprocs=1):
    logger.info(f'proj="{proj}" nprocs={nprocs}')
    print(f'proj="{proj}" nprocs={nprocs}')

    tasks = get_tasks(root, proj, use_cache=use_cache)

    ntasks = len(tasks)
    print(f'{ntasks} tasks found')

    rows = []

    with mp.Pool(nprocs) as pool:
        for row in pool.imap(simast_wrapper, tasks, 4):
            rows.append(row)
            nrows = len(rows)
            sys.stdout.write(' {:2.2f}%\r'.format(nrows*100/ntasks))

    outfile = os.path.join(f'out-diffast-{proj}.csv')
    print(f'dumping into {outfile}...')
    with open(outfile, 'w', newline='') as outf:

        header = ['commit', 'path', 'old', 'new', 'dts_time', 'dts_sim', 'dts_col']

        writer = csv.DictWriter(outf, fieldnames=header)
        writer.writeheader()

        for row in rows:
            writer.writerow(row)


def gt_wrapper(task):
    path0 = task['path0']
    path1 = task['path1']
    st_time = get_time()
    r = text_gumtree_sim(path0, path1)
    gum_sim = r['similarity']
    gum_col = r['colored']
    gum_time = get_time() - st_time
    row = dict(task)
    del row['path0']
    del row['path1']
    row['gum_time'] = gum_time
    row['gum_sim'] = gum_sim
    row['gum_col'] = gum_col
    return row


def gt_proj_mp(root, proj, nprocs=1):
    logger.info(f'proj="{proj}" nprocs={nprocs}')
    print(f'proj="{proj}" nprocs={nprocs}')

    tasks = get_tasks(root, proj)

    ntasks = len(tasks)
    print(f'{ntasks} tasks found')

    rows = []

    with mp.Pool(nprocs) as pool:
        for row in pool.imap(gt_wrapper, tasks, 4):
            rows.append(row)
            nrows = len(rows)
            sys.stdout.write(' {:2.2f}%\r'.format(nrows*100/ntasks))

    outfile = os.path.join(f'out-gumtree-{proj}.csv')
    print(f'dumping into {outfile}...')
    with open(outfile, 'w', newline='') as outf:

        header = ['commit', 'path', 'old', 'new', 'gum_time', 'gum_sim', 'gum_col']

        writer = csv.DictWriter(outf, fieldnames=header)
        writer.writeheader()

        for row in rows:
            writer.writerow(row)


def shootout():
    root = 'samples'
    for proj in sorted(os.listdir(root)):
        shootout1(root, proj)


def diffast_all(use_cache=True):
    root = 'samples'
    for proj in sorted(os.listdir(root)):
        diffast_proj(root, proj, use_cache=use_cache)


def diffast_all_mp(use_cache=True, nprocs=1):
    root = 'samples'
    for proj in sorted(os.listdir(root)):
        diffast_proj_mp(root, proj, use_cache=use_cache, nprocs=nprocs)


def gt_all_mp(nprocs=1):
    root = 'samples'
    for proj in sorted(os.listdir(root)):
        gt_proj_mp(root, proj, nprocs=nprocs)


def gt_mp_main(use_cache=True, nprocs=1):
    mp.set_start_method('fork')
    gt_all_mp(nprocs=nprocs)


def da_mp_main(use_cache=True, nprocs=1):
    mp.set_start_method('fork')
    diffast_all_mp(use_cache=use_cache, nprocs=nprocs)


def main(projs, samples_dir='samples', use_cache=True, nprocs=1,
         run_sloccount=True, run_gumtree=True, run_diffast=True):

    if nprocs == 1:  # single process
        if run_gumtree and run_diffast:
            for proj in projs:
                shootout1(samples_dir, proj)
        else:
            if run_sloccount:
                logger.info('running sloccount...')
                print('running sloccount...')
                for proj in projs:
                    sloccount_proj(samples_dir, proj)

            if run_gumtree:
                logger.info('running gumtree...')
                print('running gumtree...')
                for proj in projs:
                    gt_proj(samples_dir, proj)

            if run_diffast:
                logger.info('running diffast...')
                print('running diffast...')
                for proj in projs:
                    diffast_proj(samples_dir, proj)

    else:  # multiprocess
        mp.set_start_method('fork')

        if run_sloccount:
            logger.info('running sloccount...')
            print('running sloccount...')
            for proj in projs:
                sloccount_proj_mp(samples_dir, proj, nprocs=nprocs)

        if run_gumtree:
            logger.info('running gumtree...')
            print('running gumtree...')
            for proj in projs:
                gt_proj_mp(samples_dir, proj, nprocs=nprocs)

        if run_diffast:
            logger.info('running diffast...')
            print('running diffast...')
            for proj in projs:
                diffast_proj_mp(samples_dir, proj, use_cache=use_cache,
                                nprocs=nprocs)

    if run_sloccount and run_gumtree and run_diffast:
        merge_results()
        merge_csvs()
        conv_all()


def mkargparser():
    from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter

    parser = ArgumentParser(description='compare AST differencing tools',
                            formatter_class=ArgumentDefaultsHelpFormatter)

    parser.add_argument('-p', '--nprocs', dest='nprocs', type=int,
                        default=NPROCS,
                        help='specify number of processes')

    parser.add_argument('-c', '--use-cache', dest='use_cache',
                        action='store_true', help='use cache')

    parser.add_argument('--gumtree', action='store_true',
                        help='run gumtree only')

    parser.add_argument('--diffast', action='store_true',
                        help='run diffast only')

    parser.add_argument('--sloccount', action='store_true',
                        help='run sloccount only')

    parser.add_argument('--proj', dest='projs', metavar='PROJ', nargs='*',
                        default=PROJECTS, choices=PROJECTS,
                        help='specify project(s)')

    parser.add_argument('-d', '--debug', dest='debug', action='store_true',
                        help='enable debug printing')

    parser.add_argument('-v', '--verbose', dest='verbose', action='store_true',
                        help='enable verbose printing')

    return parser


if __name__ == '__main__':
    parser = mkargparser()
    args = parser.parse_args()

    log_level = logging.WARNING
    if args.verbose:
        log_level = logging.INFO
    if args.debug:
        log_level = logging.DEBUG

    log_file = 'shootout.log'
    LOG_FMT = '[%(asctime)s][%(levelname)s][%(module)s][%(funcName)s]'
    LOG_FMT += ' %(message)s'

    fh = logging.FileHandler(log_file, mode='w', encoding='utf-8')
    fh.setLevel(log_level)
    fmt = logging.Formatter(LOG_FMT)
    fh.setFormatter(fmt)
    logging.basicConfig(level=log_level, handlers=[fh])
    logger.addHandler(fh)

    if not args.gumtree and not args.diffast and not args.sloccount:
        run_gumtree = True
        run_diffast = True
        run_sloccount = True
    else:
        run_gumtree = args.gumtree
        run_diffast = args.diffast
        run_sloccount = args.sloccount

    if args.nprocs < 1:
        logger.error('invalid number of processes: {}'.format(args.nprocs))

    main(args.projs, use_cache=args.use_cache, nprocs=args.nprocs,
         run_sloccount=run_sloccount,
         run_gumtree=run_gumtree, run_diffast=run_diffast)
