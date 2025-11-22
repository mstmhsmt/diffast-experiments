#!/usr/bin/env python3

import os
import csv
import re
import gzip
import time
import simplejson as json
from subprocess import run
import logging

logger = logging.getLogger()


DIFFAST_CMD = '/opt/cca/bin/diffast_.exe'


HEADER = ('fileId',
          'commitId',
          'filePath',
          'algorithm',
          'startPos',
          'isSrc',
          'stmtType',
          'srcStmtLine',
          'dstStmtLine',
          'stmt-inaccurate',
          'token-inaccurate', 'extra0', 'extra1')

KEY_FIELDS = ('fileId', 'commitId', 'filePath', 'isSrc', 'stmtType', 'startPos')

FILE_NAME_PAT = re.compile(r'^results(?P<section>[0-9]+)-(?P<annotator>[0-9]+).csv$')

ORIG_ALGO_LIST = ['gt', 'mtdiff', 'ijm']
ALGO_LIST = ORIG_ALGO_LIST + ['da']

EXTRA_RESULTS_FILE = 'extra_results.csv'

SUFFIX_LIST = ['Statement', 'Declaration', 'Body']
INCLUDE_LIST = ['Block', 'CatchClause']


def check_label(target_lab, lab):
    b = any([lab.endswith(suffix) for suffix in SUFFIX_LIST]) or lab in INCLUDE_LIST
    if not b and target_lab.endswith('Invocation'):
        b = lab.endswith('Invocation')
    return b


def diffast(path0, path1, keep_going=False, use_cache=False, cache_dir=None):
    # opts = ' -dump:delta -dump:delta:minimize:more'
    opts = ''
    if keep_going:
        opts += ' -k'
    if not use_cache:
        opts += ' -clearcache'
    if cache_dir is not None:
        opts += f' -cache {cache_dir}'

    d = []
    cmd = f'{DIFFAST_CMD}{opts} {path0} {path1}'
    p = run(cmd, shell=True, capture_output=True)
    if p.returncode == 0:
        opts = ''
        if cache_dir is not None:
            opts += f' -cache {cache_dir}'
        cmd = f'{DIFFAST_CMD}{opts} -getcache {path0} {path1}'
        p = run(cmd, shell=True, capture_output=True, text=True)
        json_path = os.path.join(p.stdout.strip(), 'map.json.gz')
        logger.debug('  json_path={}'.format(json_path))
        count = 1
        while True:
            try:
                with gzip.open(json_path, 'r') as f:
                    d = json.load(f)
                    break
            except Exception:
                if count < 3:
                    logger.error(f'failed to load {json_path}, retrying ({count})...')
                    time.sleep(2*count)
                else:
                    raise
                count += 1
    else:
        logger.error(f'failed to execute {cmd}')
    return d


def get_field(d, k):
    x = d[k]
    try:
        x = int(x)
    except Exception:
        pass
    return x


class Evaluator(object):

    def __init__(self, records_path, samples_path, cache_dir=None):
        self.records_path = records_path
        self.samples_path = samples_path
        self.index_tbl = {}
        self.record_tbl = {}
        self.record_count = 0
        self.file_ids = set()
        self.cache_dir = cache_dir

        logger.info('creating index table...')

        for proj in os.listdir(samples_path):
            idx_path = os.path.join(samples_path, proj, 'index.csv')
            with open(idx_path, newline='') as f:
                for row in csv.DictReader(f):
                    key = (row['commit'], row['path'])
                    self.index_tbl[key] = (proj, row['old'], row['new'])

        logger.info('done.')

    def load_record(self, annotator, csv_path):
        with open(csv_path, newline='', errors='replace') as f:
            # reader = csv.DictReader(f)
            reader = csv.DictReader(f, fieldnames=HEADER)
            reader.__next__()
            for row in reader:
                self.record_count += 1
                key = tuple([get_field(row, k) for k in KEY_FIELDS])
                fid = int(row['fileId'])
                self.file_ids.add(fid)
                stmt_inacc = row['stmt-inaccurate']
                try:
                    stmt_inacc = int(stmt_inacc)
                except Exception:
                    pass
                token_inacc = row['token-inaccurate']
                try:
                    token_inacc = int(token_inacc)
                except Exception:
                    pass

                d = {'annotator': annotator,
                     'algorithm': row['algorithm'],
                     'srcStmtLine': int(row['srcStmtLine']),
                     'dstStmtLine': int(row['dstStmtLine']),
                     'stmt-inaccurate': stmt_inacc,
                     'token-inaccurate': token_inacc,
                     }

                try:
                    self.record_tbl[key].append(d)
                except KeyError:
                    self.record_tbl[key] = [d]

    def load_records(self):
        self.record_count = 0
        self.file_ids.clear()
        for fn in sorted(os.listdir(self.records_path)):
            m = FILE_NAME_PAT.match(fn)
            if m:
                # section = m.group('section')
                annotator = m.group('annotator')
                path = os.path.join(self.records_path, fn)
                try:
                    self.load_record(annotator, path)
                except Exception:
                    logger.error(f'failed to load {path}')
                    raise

        if os.path.exists(EXTRA_RESULTS_FILE):
            logger.info(f'loading {EXTRA_RESULTS_FILE}...')
            try:
                self.load_record('x', EXTRA_RESULTS_FILE)
                logger.info('done.')
            except Exception:
                logger.error(f'failed to load {EXTRA_RESULTS_FILE}')
                raise

    def clear_disp(self):
        self.disp = []

    def get_disp(self):
        return self.disp

    def pr(self, mes):
        self.disp.append(mes)
        print(mes)

    def eval(self, use_cache=False):
        count = 0
        missing_annot_count_tbl = {'gt': 0, 'mtdiff': 0, 'ijm': 0, 'da': 0}
        extra_annot_count_tbl = {'gt': 0, 'mtdiff': 0, 'ijm': 0, 'da': 0}
        inacc_count_tbl = {'gt': 0, 'mtdiff': 0, 'ijm': 0, 'da': 0}

        missing_tbl = {}

        for k in sorted(self.record_tbl.keys()):
            count += 1
            d = dict(zip(KEY_FIELDS, k))
            commitId = d['commitId']
            filePath = d['filePath']
            startPos = d['startPos']
            stmtType = d['stmtType']

            proj, fn0, fn1 = self.index_tbl[(commitId, filePath)]

            self.clear_disp()

            self.pr(f'[{count}] {proj}:{commitId}:{filePath}:{startPos}:{stmtType}')

            path0 = os.path.join(self.samples_path, proj, '0', fn0)
            path1 = os.path.join(self.samples_path, proj, '1', fn1)

            self.pr(f'  {path0} {path1}')

            diffast_map = diffast(path0, path1, use_cache=use_cache,
                                  cache_dir=self.cache_dir)

            dst_tbl = {}

            src_dst_set = set()

            record = self.record_tbl[k]

            srcStmtLines = set()
            dstStmtLines = set()

            for a in record:
                srcStmtLine = a['srcStmtLine']
                dstStmtLine = a['dstStmtLine']
                if srcStmtLine >= 0 and srcStmtLine not in srcStmtLines:
                    self.pr('  srcStmtLine={}'.format(srcStmtLine))
                    srcStmtLines.add(srcStmtLine)
                elif dstStmtLine >= 0 and dstStmtLine not in dstStmtLines:
                    self.pr('  dstStmtLine={}'.format(dstStmtLine))
                    dstStmtLines.add(dstStmtLine)

            for src, dst in diffast_map:
                src_so = src['start_offset']
                src_sl = src['start_line']
                src_lab = src['label']
                dst_sl = dst['start_line']
                dst_lab = dst['label']

                if check_label(stmtType, src_lab) and check_label(stmtType, dst_lab):
                    if src_so == startPos or src_sl in srcStmtLines or dst_sl in dstStmtLines:
                        src_dst_set.add((src_sl, dst_sl))
                        self.pr(f'  [da] {src_lab}:{src_sl} --> {dst_sl}')
                        dst_tbl[dst_sl] = src_sl, dst_lab

            al_ = []

            src_tbl = dict(src_dst_set)

            inacc_gotten_flag_tbl = {'1': False, '2': False, '3': False}

            count_tbl = {'gt': 0, 'mtdiff': 0, 'ijm': 0}

            inv_put_set = set()

            no_extra_flag = True

            for a in sorted(record, key=lambda x: x['algorithm']):
                annotator = a['annotator']
                algo = a['algorithm']
                inacc = a['stmt-inaccurate']

                if algo == 'da':
                    no_extra_flag = False
                    if inacc == 1:
                        inacc_count_tbl[algo] += 3
                else:
                    count_tbl[algo] += 1

                    if inacc == 1:
                        inacc_count_tbl[algo] += 1

                    a_srcStmtLine = a['srcStmtLine']
                    a_dstStmtLine = a['dstStmtLine']

                    if a_dstStmtLine not in inv_put_set and a_dstStmtLine >= 0:
                        self.pr('  [da] {} <-- {}:{}'
                                .format(*dst_tbl.get(a_dstStmtLine, (None, None)),
                                        a_dstStmtLine))
                        inv_put_set.add(a_dstStmtLine)

                    cond0 = (a_srcStmtLine, a_dstStmtLine) in src_dst_set
                    cond1 = a_srcStmtLine < 0 and dst_tbl.get(a_dstStmtLine, None) is None
                    cond2 = a_srcStmtLine >= 0 and \
                        src_tbl.get(a_srcStmtLine, None) is None and a_dstStmtLine < 0
                    if cond0 or cond1 or cond2:
                        if not inacc_gotten_flag_tbl[annotator]:
                            a_ = dict(a)
                            a_['algorithm'] = 'da'
                            al_.append(a_)
                            if inacc == 1:
                                inacc_gotten_flag_tbl[annotator] = True

                judgment = ' INACCURATE' if inacc == 1 else ''
                self.pr(f'  {a}{judgment}')

            for alg, cnt in count_tbl.items():
                if cnt < 3:
                    missing_annot_count_tbl[alg] += 3 - cnt
                elif cnt > 3:
                    extra_annot_count_tbl[alg] += cnt - 3

            if no_extra_flag:
                for a_ in al_:
                    inacc_ = a_['stmt-inaccurate']

                    if inacc_ == 1:
                        inacc_count_tbl['da'] += 1

                    judgment_ = ' INACCURATE' if inacc_ == 1 else ''
                    self.pr(f'  {a_}{judgment_}')

                if len(al_) < 3:
                    mac = 3 - len(al_)
                    logger.info(f'[{count}] missing_annot_count_tbl[da] += {mac}')
                    missing_annot_count_tbl['da'] += mac
                    missing_tbl[count] = self.get_disp()

        print('----------------------------')

        for k in sorted(missing_tbl.keys()):
            print('\n'.join(missing_tbl[k]))

        print('----------------------------')

        total = count * 3

        missing_file_ids = set()
        for i in range(1, max(self.file_ids)+1):
            if i not in self.file_ids:
                missing_file_ids.add(i)

        print(f'* {self.record_count} records found')
        print(f'* missing file ids: {missing_file_ids}')
        print(f'* Examples: {count}')
        print(f'* Expected annotations per algorithm: {total}')

        print('* Missing annotations:')
        for algo in ALGO_LIST:
            print('    {}: {}'.format(algo, missing_annot_count_tbl[algo]))

        print('* Extra annotations:')
        for algo in ORIG_ALGO_LIST:
            print('    {}: {}'.format(algo, extra_annot_count_tbl[algo]))

        print('* Inaccurate mappings:')
        for algo in ALGO_LIST:
            if missing_annot_count_tbl[algo] == 0:
                print('    {}: {}'.format(algo, inacc_count_tbl[algo]))

        print('* Inaccurate mapping rate:')
        for algo in ALGO_LIST:
            if missing_annot_count_tbl[algo] == 0:
                ic = inacc_count_tbl[algo]
                r = float(ic * 100) / float(total)
                print(f'    {algo}: {ic}/{total}={r:3.2f}%')


class Evaluator2(object):
    def __init__(self, summary_path, samples_path, cache_dir=None):
        self.summary_path = summary_path
        self.samples_path = samples_path
        self.index_tbl = {}
        self.proj_tbl = None
        self.cache_dir = cache_dir

        logger.info('creating index table...')
        for proj in os.listdir(samples_path):
            idx_path = os.path.join(samples_path, proj, 'index.csv')
            with open(idx_path, newline='') as f:
                for row in csv.DictReader(f):
                    key = (row['commit'], row['path'])
                    self.index_tbl[key] = (proj, row['old'], row['new'])
        logger.info('done.')

        logger.info('loading experts\' results summary')
        with open(self.summary_path) as f:
            self.proj_tbl = json.load(f)
        logger.info('done.')

    def eval(self, use_cache=True):
        count = 0

        count_tbl = {'gt': 0, 'mtdiff': 0, 'ijm': 0, 'da': 0}

        for proj, t0 in self.proj_tbl.items():
            for commit, t1 in t0.items():
                for fpath, t2 in t1.items():
                    for startPos, d in t2.items():

                        srcStmtLine = d.get('srcStmtLine', None)
                        dstStmtLine = d.get('dstStmtLine', None)
                        stmtType = d['stmtType']

                        if srcStmtLine is not None and dstStmtLine is not None:
                            count += 1

                            jl = d['judgments']

                            algos = set()

                            gt_add = 0

                            for j in jl:
                                algo = j['algo']
                                if algo not in algos:
                                    algos.add(algo)
                                    if j['srcStmtLine'] == srcStmtLine and \
                                       j['dstStmtLine'] == dstStmtLine:
                                        count_tbl[algo] += 1
                                        if algo == 'gt':
                                            gt_add = 1

                            proj, fn0, fn1 = self.index_tbl[(commit, fpath)]

                            path0 = os.path.join(self.samples_path, proj, '0', fn0)
                            path1 = os.path.join(self.samples_path, proj, '1', fn1)

                            diffast_map = diffast(path0, path1,
                                                  use_cache=use_cache,
                                                  cache_dir=self.cache_dir)

                            da_add = 0
                            da_has_map = False

                            for src, dst in diffast_map:
                                # src_so = src['start_offset']
                                src_sl = src['start_line']
                                src_lab = src['label']
                                dst_sl = dst['start_line']
                                dst_lab = dst['label']

                                if check_label(stmtType, src_lab) and \
                                   check_label(stmtType, dst_lab):
                                    if src_sl == srcStmtLine and dst_sl == dstStmtLine:
                                        da_add = 1
                                        break
                                    elif src_sl == srcStmtLine or dst_sl == dstStmtLine:
                                        da_has_map = True

                            if da_add == 0 and not da_has_map and \
                               (srcStmtLine < 0 or dstStmtLine < 0):
                                da_add = 1

                            if da_add == 0 and gt_add == 1:
                                logger.warning(f'{proj}:{commit}:{fpath}:{startPos}:'
                                               f'{srcStmtLine}-{dstStmtLine}')
                                logger.warning(f'  {path0} {path1}')

                            count_tbl['da'] += da_add

        for algo, c in count_tbl.items():
            print('{}: {}/{} ({:.2f}%)'.format(algo, c, count, 100*c/count))


def main():
    logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
    e = Evaluator('DifferentialTesting/expert-results', 'samples', 'CACHE')
    e.load_records()
    e.eval(use_cache=True)
    # e.eval(use_cache=False)


def main2():
    e = Evaluator2('DifferentialTesting/expert-results/summary.json',
                   'samples', 'CACHE')
    # e.eval(use_cache=True)
    e.eval(use_cache=False)


if __name__ == '__main__':
    main()
    # main2()
