#!/usr/bin/env python3

import sys
import os
import re
# import json
import simplejson as json
from subprocess import run

import time
import multiprocessing as mp
import math
import psutil

from sloccount import escape

logger = mp.get_logger()

GUMTREE_DIR = '/root/direct/GumTreeDiff'
GUMTREE_CMD = os.path.join(GUMTREE_DIR, 'run.sh')

SIMAST_CMD = '/opt/cca/bin/simast_.exe'

SLOCCOUNT_CACHE_NAME = 'CACHE-sloccount'

EXCLUDED_TYPES_TBL = {
    'java': ['Javadoc', 'TagElement', 'TextElement'],
    'python': [],  # ['comment']
}

MAX_NRETRIES = 3

MAX_CPU_COUNT = 128

IGNORE_MOVE = True


try:
    NPROCS = min(psutil.cpu_count(logical=False), MAX_CPU_COUNT)
except Exception:
    NPROCS = os.cpu_count()


def get_lang(fn):
    lang = '?'
    if fn.endswith('.py'):
        lang = 'python'
    elif fn.endswith('.java'):
        lang = 'java'
    return lang


def get_excluded_types(lang):
    return EXCLUDED_TYPES_TBL.get(lang, [])


def get_time():
    return time.monotonic()


def load_json(path):
    d = None
    with open(path) as f:
        d = json.load(f)
    return d


PAT = re.compile(r'^(?P<type>.*)\[(?P<start>[0-9]+),(?P<end>[0-9]+)\]$', flags=re.DOTALL)


class GtHandler(object):
    def __init__(self, path):
        self.lang = get_lang(path)
        self.excluded_types = get_excluded_types(self.lang)

    def check_tree(self, tree, ty_st_ed):
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

    def find_subtree(self, tree, ty_st_ed):
        if self.check_tree(tree, ty_st_ed):
            return tree

        for c in tree['children']:
            r = self.find_subtree(c, ty_st_ed)
            if r is not None:
                return r

        return None

    def count_nodes(self, nd):
        count = 1

        if nd['type'] in self.excluded_types:
            return 0

        for c in nd['children']:
            count += self.count_nodes(c)

        return count

    def count_tree_nodes(self, tree):
        root = tree['root']
        c = self.count_nodes(root)
        return c

    def get_info(self, lab):
        res = None

        if any([lab.startswith(t) for t in self.excluded_types]):
            return res

        m = PAT.match(lab)
        if m:
            ty = m.group('type').rstrip()
            st = int(m.group('start'))
            ed = int(m.group('end'))
            res = (ty, st, ed)
        return res

    def get_node_region(self, nd):
        r = set()
        st = int(nd['pos'])
        ed = st + int(nd['length'])
        r = set(range(st, ed))
        for c in nd['children']:
            r.update(self.get_node_region(c))
        return r

    def get_tree_region(self, tree):
        root = tree['root']
        r = self.get_node_region(root)
        return r

    def get_region(self, lab):
        r = None
        if any([lab.startswith(t) for t in self.excluded_types]):
            return r
        m = PAT.match(lab)
        if m:
            st = int(m.group('start'))
            ed = int(m.group('end'))
            r = set(range(st, ed))
        return r

    def get_matches(self, diff):
        matches = set()
        for m in diff['matches']:
            if any([m['src'].startswith(t) or m['dest'].startswith(t)
                    for t in self.excluded_types]):
                logger.debug(f'excluded: {m}')
            else:
                info = self.get_info(m['src'])
                matches.add(info)
        return matches

    def get_nodes(self, subtree):
        infos = set()

        if subtree['type'] in self.excluded_types:
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
            infos.update(self.get_nodes(c))

        return infos

    def similarity(self, src_tree, dst_tree, diff):
        src_sz = self.count_tree_nodes(src_tree)
        dst_sz = self.count_tree_nodes(dst_tree)

        matches = self.get_matches(diff)

        logger.debug(f'src_sz={src_sz} dst_sz={dst_sz} nmatches={len(matches)}')

        moved_nodes = set()
        updated_nodes = set()
        deleted_nodes = set()

        for a in diff['actions']:
            act = a['action']
            if act == 'update-node':
                info = self.get_info(a['tree'])
                if info is not None:
                    updated_nodes.add(info)

            elif act == 'delete-node':
                info = self.get_info(a['tree'])
                if info is not None:
                    deleted_nodes.add(info)

            elif act == 'delete-tree':
                info = self.get_info(a['tree'])
                if info is not None:
                    subtree = self.find_subtree(src_tree['root'], info)
                    if subtree is not None:
                        deleted_nodes.update(self.get_nodes(subtree))
                    else:
                        logger.debug('not found: {} {} {}'.format(*info))

            elif act == 'move-tree':
                info = self.get_info(a['tree'])
                if info is not None:
                    subtree = self.find_subtree(src_tree['root'], info)
                    if subtree is not None:
                        moved_nodes.update(self.get_nodes(subtree))
                    else:
                        logger.debug('not found: {} {} {}'.format(*info))

        matches.difference_update(moved_nodes | updated_nodes | deleted_nodes)
        nmatches = len(matches)

        sim = 2.0 * nmatches / (src_sz + dst_sz)

        return sim

    def delta(self, src_tree, dst_tree, diff):
        matches = self.get_matches(diff)
        cost = 0
        nrelabels = 0
        for a in diff['actions']:
            act = a['action']
            if act == 'update-node':
                info = self.get_info(a['tree'])
                if info is not None:
                    cost += 1
                    nrelabels += 1

            elif act == 'delete-node':
                info = self.get_info(a['tree'])
                if info is not None:
                    cost += 1

            elif act == 'delete-tree':
                info = self.get_info(a['tree'])
                if info is not None:
                    subtree = self.find_subtree(src_tree['root'], info)
                    if subtree is not None:
                        cost += len(self.get_nodes(subtree))
                    else:
                        logger.debug('not found: {} {} {}'.format(*info))

            elif act == 'insert-node':
                info = self.get_info(a['tree'])
                if info is not None:
                    cost += 1

            elif act == 'insert-tree':
                info = self.get_info(a['tree'])
                if info is not None:
                    subtree = self.find_subtree(dst_tree['root'], info)
                    if subtree is not None:
                        nnl = len(self.get_nodes(subtree))
                        logger.debug(f'intert-tree: nnl={nnl}')
                        cost += nnl
                    else:
                        logger.debug('not found: {} {} {}'.format(*info))

            elif act == 'move-tree':
                info = self.get_info(a['tree'])
                if info is not None:
                    cost += 1

        nmatches = len(matches)
        logger.debug(f'cost={cost} nmatches={nmatches}')

        r = {'cost': cost, 'nmappings': nmatches, 'nrelabels': nrelabels}

        return r

    def get_reg(self, lab):
        r = None
        m = PAT.match(lab)
        if m:
            st = int(m.group('start'))
            ed = int(m.group('end'))
            r = (st, ed)
        else:
            logger.warning(f'failed to get region: lab={lab}')
        return r

    def get_region_mapping(self, diff):
        tbl = {}
        for x in diff['matches']:
            if any([x['src'].startswith(t) or x['dest'].startswith(t)
                    for t in self.excluded_types]):
                logger.debug(f'excluded: {x}')
                continue
            src = self.get_reg(x['src'])
            dst = self.get_reg(x['dest'])
            if src and dst:
                tbl[src] = dst
        return tbl

    def get_mapped_region(self, lab, mapping):
        src_reg = self.get_reg(lab)
        dst_reg = mapping[src_reg]
        # logger.debug(f'{src_reg} --> {dst_reg}')
        r = set(range(*dst_reg))
        return r

    def text_similarity(self,
                        src_tree, dst_tree, diff,
                        align0, align1,
                        src_region_sz=None, dst_region_sz=None,
                        ignore_move=IGNORE_MOVE):

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

        mapping = self.get_region_mapping(diff)

        for a in diff['actions']:
            act = a['action']
            lab = a['tree']
            if act == 'update-node':
                r = self.get_region(lab)
                if r is not None:
                    src_colored_region.update(r)
                    dst_colored_region.update(self.get_mapped_region(lab, mapping))

            elif act == 'delete-node':
                r = self.get_region(lab)
                if r is not None:
                    src_colored_region.update(r)

            elif act == 'delete-tree':
                r = self.get_region(lab)
                if r is not None:
                    src_colored_region.update(r)

            elif act == 'insert-node':
                r = self.get_region(lab)
                if r is not None:
                    dst_colored_region.update(r)

            elif act == 'insert-tree':
                r = self.get_region(lab)
                if r is not None:
                    dst_colored_region.update(r)

            elif act == 'move-tree':
                if not ignore_move:
                    r = self.get_region(lab)
                    if r is not None:
                        src_colored_region.update(r)
                        dst_colored_region.update(self.get_mapped_region(lab, mapping))

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


def gumtree_diff(path0, path1, matcher='gumtree-simple'):
    opts = f' -m {matcher}'
    if path0.endswith('.py'):
        opts += ' -g python-treesitter-ng'
    cmd = f'{GUMTREE_CMD} textdiff{opts} -f json {escape(path0)} {escape(path1)}'
    logger.debug(f'cmd={cmd}')
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
    opts = ''
    if path.endswith('.py'):
        opts += ' -g python-treesitter-ng'
    cmd = f'{GUMTREE_CMD} parse{opts} -f json {escape(path)}'
    tree = None
    try:
        p = run(cmd, shell=True, capture_output=True)
        tree = json.loads(p.stdout)
    except Exception as e:
        logger.error(f'{path}: {e} (opts="{opts}")')
    return tree


def gumtree_node_count(path):
    c = None
    t = gumtree_parse(path)
    if t is not None:
        gt = GtHandler(path)
        c = gt.count_tree_nodes(t)
    return c


def gumtree_sim(path0, path1):
    t0 = gumtree_parse(path0)
    t1 = gumtree_parse(path1)
    d = gumtree_diff(path0, path1)
    gt = GtHandler(path0)
    sim = gt.similarity(t0, t1, d)
    return round(sim, 6)


def gumtree_dist(path0, path1):
    t0 = gumtree_parse(path0)
    t1 = gumtree_parse(path1)
    d = gumtree_diff(path0, path1)
    gt = GtHandler(path0)
    r = gt.delta(t0, t1, d)
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
                gt = GtHandler(path0)
                r = gt.delta(t0, t1, d)
    return r


def text_gumtree_sim(path0, path1):
    t0 = gumtree_parse(path0)
    t1 = gumtree_parse(path1)
    d = gumtree_diff(path0, path1)
    try:
        align0 = get_token_regions(path0)
        align1 = get_token_regions(path1)
        gt = GtHandler(path0)
        r0 = gt.text_similarity(t0, t1, d, align0, align1)
        sim = r0['similarity']
        col = r0['colored']
        r1 = gt.delta(t0, t1, d)
        cost = r1['cost']
    except Exception as e:
        logger.error(f'{path0} {path1}: {e}')
        raise
    logger.debug(f'sim={sim} col={col} cost={cost}')
    return {'similarity': round(sim, 6), 'colored': col, 'cost': cost}


def diffast_sim(path0, path1):
    cmd = f'{SIMAST_CMD} -clearcache {escape(path0)} {escape(path1)}'
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


def read_diff_json(diff_json, align0, align1, ignore_move=IGNORE_MOVE):
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
                elif tag == 'MOVE':
                    if not ignore_move:
                        r0.update(get_seg_region0(h))
                        r1.update(get_seg_region1(h))
                elif tag == 'MOVREL':
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


DIFFTS_COST_PAT = re.compile(r'total changes\s*: ([0-9]+)')
DIFFTS_NMAP_PAT = re.compile(r'mapping size\s*: ([0-9]+)')
DIFFTS_INSERT_PAT = re.compile(r'inserts\s*: ([0-9]+)')
DIFFTS_DELETE_PAT = re.compile(r'deletes\s*: ([0-9]+)')
DIFFTS_RELABEL_PAT = re.compile(r'relabels\s*: ([0-9]+)')
DIFFTS_MOVE_PAT = re.compile(r'moves\s*: ([0-9]+)\([0-9]+\)')
DIFFTS_MOVREL_PAT = re.compile(r'movrels\s*: ([0-9]+)\([0-9]+\)')
DIFFTS_NNODES1_PAT = re.compile(r'nnodes1\s*: ([0-9]+)')
DIFFTS_NNODES2_PAT = re.compile(r'nnodes2\s*: ([0-9]+)')


def set_value(result, key, pat, line):
    m = pat.search(line)
    if m:
        try:
            result[key] = int(m.group(1))

        except Exception:
            logger.warning(f'cannot get value: key="{key}" line="{line}"')


def read_stat(stat_path):
    r = {'cost': 0,
         'nmappings': 0,
         'ninserts': 0,
         'ndeletes': 0,
         'nrelabels': 0,
         'nmoves': 0,
         'nmovrels': 0,
         'nnodes1': 0,
         'nnodes2': 0,
         }
    name_pat_list = [('cost', DIFFTS_COST_PAT),
                     ('nmappings', DIFFTS_NMAP_PAT),
                     ('ninserts', DIFFTS_INSERT_PAT),
                     ('ndeletes', DIFFTS_DELETE_PAT),
                     ('nrelabels', DIFFTS_RELABEL_PAT),
                     ('nmoves', DIFFTS_MOVE_PAT),
                     ('nmovrels', DIFFTS_MOVREL_PAT),
                     ('nnodes1', DIFFTS_NNODES1_PAT),
                     ('nnodes2', DIFFTS_NNODES2_PAT),
                     ]
    try:
        with open(stat_path) as f:
            for line in f:
                for (name, pat) in name_pat_list:
                    set_value(r, name, pat, line)
            return r

    except IOError as e:
        logger.warning(f'{e}')
        return None


def read_stat_json(stat_json):
    r = {'cost': 0,
         'nmappings': 0,
         'ninserts': 0,
         'ndeletes': 0,
         'nrelabels': 0,
         'nmoves': 0,
         'nmovrels': 0,
         'nnodes1': 0,
         'nnodes2': 0,
         }
    with open(stat_json, 'r') as f:
        try:
            d = json.load(f)
            r = {}
            r['cost'] = d['edit_cost']
            r['nmappings'] = d['nmappings']
            r['ninserts'] = d['inserts']
            r['ndeletes'] = d['deletes']
            r['nrelabels'] = d['relabels']
            r['nmoves'] = d['moves']
            r['nmovrels'] = d['move+relabels']
            r['nnodes1'] = d['nnodes1']
            r['nnodes2'] = d['nnodes2']
            return r
        except Exception as e:
            logger.error(f'invalid JSON file: {stat_json}: {e}')
            return None


def text_diffast_sim(path0, path1,
                     keep_going=False,
                     scan_huge_arrays=False,
                     no_rr=False,
                     weak=False,
                     use_cache=True, cache_dir=None):

    worker_id = mp.current_process().name

    opt = ''
    if keep_going:
        opt += ' -k'
    if scan_huge_arrays:
        opt += ' -scan-huge-arrays'
    if no_rr:
        opt += ' -norr'
    if weak:
        opt += ' -weak'
    if not use_cache:
        opt += ' -clearcache'
    if cache_dir is not None:
        opt += f' -cache {cache_dir}'

    opt += f' -localcachename {worker_id}'

    path0_ = escape(path0)
    path1_ = escape(path1)

    cmd0 = f'{SIMAST_CMD}{opt} {path0_} {path1_}'
    p = run(cmd0, shell=True, capture_output=True)

    if str(p.stdout).strip() == '1.0':
        return {'similarity': 1.0, 'colored': 0, 'cost': 0}

    opt = ''
    if cache_dir is not None:
        opt += f' -cache {cache_dir}'

    cmd1 = f'{SIMAST_CMD}{opt} -getcache -localcachename {worker_id} {path0_} {path1_}'
    p = run(cmd1, shell=True, capture_output=True, text=True)

    cache_dir = p.stdout.strip()
    diff_json = os.path.join(cache_dir, 'diff.json')
    stat = None

    stat_path = os.path.join(cache_dir, 'stat.json')
    if not os.path.exists(stat_path):
        logger.warning(f'not found: {stat_path}')
        logger.warning(f'failed to compare: {path0} {path1}')
        logger.warning(f'cmd: {cmd0}')
        return {'similarity': 0.0, 'colored': math.nan, 'cost': math.nan}

    cost = -1
    stat = read_stat_json(stat_path)
    if stat:
        cost = stat['cost']
        if cost == 0:
            return {'similarity': 1.0, 'colored': 0, 'cost': 0}

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

    return {'similarity': round(sim, 6), 'colored': colored, 'cost': cost}


def gt_main():
    import logging
    from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter

    parser = ArgumentParser(description='GumTree(TextSimilarity)',
                            formatter_class=ArgumentDefaultsHelpFormatter)

    parser.add_argument('original', type=str, metavar='ORIGINAL',
                        help='original source file')

    parser.add_argument('modified', type=str, metavar='MODIFIED',
                        help='modified source file')

    parser.add_argument('-d', '--debug', dest='debug', action='store_true',
                        help='enable debug printing')

    parser.add_argument('-v', '--verbose', dest='verbose', action='store_true',
                        help='enable verbose printing')

    args = parser.parse_args()

    log_level = logging.WARNING
    if args.verbose:
        log_level = logging.INFO
    if args.debug:
        log_level = logging.DEBUG

    log_file = 'gt.log'
    LOGGING_FORMAT = '[%(asctime)s][%(levelname)s][%(module)s][%(funcName)s] %(message)s'

    fh = logging.FileHandler(log_file, mode='w', encoding='utf-8')
    fh.setLevel(log_level)
    fmt = logging.Formatter(LOGGING_FORMAT)
    fh.setFormatter(fmt)
    logging.basicConfig(level=log_level, handlers=[fh])
    logger.addHandler(fh)

    # sim = gumtree_sim(args.original, args.modified)
    r = text_gumtree_sim(args.original, args.modified)
    print(r)


def da_main():
    import logging
    from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter

    parser = ArgumentParser(description='Diff/AST(TextSimilarity)',
                            formatter_class=ArgumentDefaultsHelpFormatter)

    parser.add_argument('original', type=str, metavar='ORIGINAL',
                        help='original source file')

    parser.add_argument('modified', type=str, metavar='MODIFIED',
                        help='modified source file')

    parser.add_argument('--cache-dir', dest='cache_dir', metavar='DIR',
                        default='CACHE', help='specify cache dir')

    parser.add_argument('-c', '--use-cache', dest='use_cache',
                        action='store_true', help='use cache')

    parser.add_argument('-d', '--debug', dest='debug', action='store_true',
                        help='enable debug printing')

    parser.add_argument('-v', '--verbose', dest='verbose', action='store_true',
                        help='enable verbose printing')

    args = parser.parse_args()

    log_level = logging.WARNING
    if args.verbose:
        log_level = logging.INFO
    if args.debug:
        log_level = logging.DEBUG

    log_file = 'da.log'
    LOGGING_FORMAT = '[%(asctime)s][%(levelname)s][%(module)s][%(funcName)s] %(message)s'

    fh = logging.FileHandler(log_file, mode='w', encoding='utf-8')
    fh.setLevel(log_level)
    fmt = logging.Formatter(LOGGING_FORMAT)
    fh.setFormatter(fmt)
    logging.basicConfig(level=log_level, handlers=[fh])
    logger.addHandler(fh)

    r = text_diffast_sim(args.original, args.modified,
                         keep_going=True,
                         scan_huge_arrays=True,
                         no_rr=False,
                         weak=True,
                         use_cache=args.use_cache,
                         cache_dir=args.cache_dir)
    print(r)


if __name__ == '__main__':
    pass
