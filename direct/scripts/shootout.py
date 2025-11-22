#!/usr/bin/env python3

import sys
import os
import csv
import multiprocessing as mp
import logging

from common import SLOCCOUNT_CACHE_NAME, NPROCS
from common import get_time, text_gumtree_sim, text_diffast_sim
# from merge_results import merge_results
# from merge_csvs import merge_csvs
# from conv_csv import conv_all
import common
import sloccount

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

HEADER = ['commit', 'path', 'old', 'old_sloc', 'new', 'new_sloc',
          'gt_time', 'gt_sim', 'gt_col', 'gt_cost',
          'da_time', 'da_sim', 'da_col', 'da_cost',
          'ok', 'agree']


DIFFAST_SCAN_HUGE_ARRAYS = False


def sloccount_proj(root, proj):
    logger.info(f'proj="{proj}"')
    print(f'proj="{proj}"')

    outfile = os.path.join(f'out-sloc.{proj}.csv')

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


def get_tasks(root, proj, no_rr=False, use_cache=False, cache_dir=None):

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

            if no_rr:
                task['no_rr'] = True

            if use_cache:
                task['use_cache'] = True

            if cache_dir:
                task['cache_dir'] = cache_dir

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

    outfile = os.path.join(f'out-sloc.{proj}.csv')
    print(f'dumping into {outfile}...')
    with open(outfile, 'w', newline='') as outf:

        header = ['commit', 'path', 'old', 'old_sloc', 'new', 'new_sloc']

        writer = csv.DictWriter(outf, fieldnames=header)
        writer.writeheader()

        for row in rows:
            writer.writerow(row)

        logger.info(f'results dumped into {outfile}')


def shootout1(root, proj, no_rr=False, use_cache=True, cache_dir='CACHE'):
    logger.info(f'proj="{proj}"')
    print(f'proj="{proj}"')

    outfile = os.path.join(f'out-{proj}.csv')

    with open(outfile, 'w', newline='') as outf:

        header = HEADER
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
                gt_sim = r['similarity']
                gt_col = r['colored']
                gt_cost = r['cost']
                gt_time = get_time() - st_time
                logger.info(f'gt_time={gt_time}')

                st_time = get_time()
                r = text_diffast_sim(path0, path1, keep_going=True,
                                     scan_huge_arrays=DIFFAST_SCAN_HUGE_ARRAYS,
                                     no_rr=no_rr,
                                     weak=True,
                                     use_cache=use_cache, cache_dir=cache_dir)
                da_sim = r['similarity']
                da_col = r['colored']
                da_cost = r['cost']
                da_time = get_time() - st_time
                logger.info(f'da_time={da_time}')

                ok = gt_sim <= da_sim and gt_col >= da_col
                agree = gt_sim == da_sim and gt_col == da_col
                row = {'commit': commit, 'path': path,
                       'old': fn0, 'old_sloc': old_sloc,
                       'new': fn1, 'new_sloc': new_sloc,
                       'gt_time': gt_time, 'gt_sim': gt_sim, 'gt_col': gt_col,
                       'gt_cost': gt_cost,
                       'da_time': da_time, 'da_sim': da_sim, 'da_col': da_col,
                       'da_cost': da_cost,
                       'ok': ok, 'agree': agree}
                writer.writerow(row)

        logger.info(f'results dumped into {outfile}')


def gt_proj(root, proj):
    logger.info(f'proj="{proj}"')
    print(f'proj="{proj}"')

    outfile = os.path.join(f'out-gumtree.{proj}.csv')

    with open(outfile, 'w', newline='') as outf:

        header = ['commit', 'path', 'old', 'new',
                  'gt_time', 'gt_sim', 'gt_col', 'gt_cost']

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
                gt_sim = r['similarity']
                gt_col = r['colored']
                gt_cost = r['cost']
                gt_time = get_time() - st_time
                logger.info(f'gt_time={gt_time}')

                row = {'commit': commit, 'path': path,
                       'old': fn0, 'new': fn1,
                       'gt_time': gt_time, 'gt_sim': gt_sim, 'gt_col': gt_col,
                       'gt_cost': gt_cost
                       }

                writer.writerow(row)

        logger.info(f'results dumped into {outfile}')


def diffast_proj(root, proj, no_rr=False, use_cache=True, cache_dir=None):
    logger.info(f'proj="{proj}"')
    print(f'proj="{proj}"')

    outfile = os.path.join(f'out-diffast.{proj}.csv')

    with open(outfile, 'w', newline='') as outf:

        header = ['commit', 'path', 'old', 'new',
                  'da_time', 'da_sim', 'da_col', 'da_cost']

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
                                     scan_huge_arrays=DIFFAST_SCAN_HUGE_ARRAYS,
                                     no_rr=no_rr,
                                     weak=True,
                                     use_cache=use_cache, cache_dir=cache_dir)
                da_sim = r['similarity']
                da_col = r['colored']
                da_cost = r['cost']
                da_time = get_time() - st_time
                logger.info(f'da_time={da_time}')

                row = {'commit': commit, 'path': path,
                       'old': fn0, 'new': fn1,
                       'da_time': da_time, 'da_sim': da_sim, 'da_col': da_col,
                       'da_cost': da_cost,
                       }

                writer.writerow(row)

        logger.info(f'results dumped into {outfile}')


def simast_wrapper(task):
    path0 = task['path0']
    path1 = task['path1']
    no_rr = task.get('no_rr', False)
    use_cache = task.get('use_cache', False)
    cache_dir = task.get('cache_dir', None)
    st_time = get_time()
    r = text_diffast_sim(path0, path1, keep_going=True,
                         scan_huge_arrays=DIFFAST_SCAN_HUGE_ARRAYS,
                         no_rr=no_rr,
                         weak=True,
                         use_cache=use_cache, cache_dir=cache_dir)
    da_sim = r['similarity']
    da_col = r['colored']
    da_cost = r['cost']
    da_time = get_time() - st_time
    row = dict(task)
    del row['path0']
    del row['path1']
    row['da_time'] = da_time
    row['da_sim'] = da_sim
    row['da_col'] = da_col
    row['da_cost'] = da_cost
    try:
        del row['no_rr']
    except Exception:
        pass
    try:
        del row['use_cache']
    except Exception:
        pass
    try:
        del row['cache_dir']
    except Exception:
        pass
    return row


def diffast_proj_mp(root, proj, no_rr=False, use_cache=False, nprocs=1, cache_dir=None):
    logger.info(f'proj="{proj}" nprocs={nprocs}')
    print(f'proj="{proj}" nprocs={nprocs}')

    tasks = get_tasks(root, proj, no_rr=no_rr, use_cache=use_cache, cache_dir=cache_dir)

    ntasks = len(tasks)
    print(f'{ntasks} tasks found')

    rows = []

    st_time = get_time()

    with mp.Pool(nprocs) as pool:
        for row in pool.imap(simast_wrapper, tasks, 4):
            rows.append(row)
            nrows = len(rows)
            sys.stdout.write(' {:2.2f}%\r'.format(nrows*100/ntasks))

    tm = get_time() - st_time

    print(f'processed in {tm/60:.2f} min.')

    outfile = os.path.join(f'out-diffast.{proj}.csv')
    print(f'dumping into {outfile}...')
    with open(outfile, 'w', newline='') as outf:

        header = ['commit', 'path', 'old', 'new', 'da_time', 'da_sim', 'da_col', 'da_cost']

        writer = csv.DictWriter(outf, fieldnames=header)
        writer.writeheader()

        for row in rows:
            writer.writerow(row)


def gt_wrapper(task):
    path0 = task['path0']
    path1 = task['path1']
    st_time = get_time()
    r = text_gumtree_sim(path0, path1)
    gt_sim = r['similarity']
    gt_col = r['colored']
    gt_cost = r['cost']
    gt_time = get_time() - st_time
    row = dict(task)
    del row['path0']
    del row['path1']
    row['gt_time'] = gt_time
    row['gt_sim'] = gt_sim
    row['gt_col'] = gt_col
    row['gt_cost'] = gt_cost
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

    outfile = os.path.join(f'out-gumtree.{proj}.csv')
    print(f'dumping into {outfile}...')
    with open(outfile, 'w', newline='') as outf:

        header = ['commit', 'path', 'old', 'new', 'gt_time', 'gt_sim', 'gt_col', 'gt_cost']

        writer = csv.DictWriter(outf, fieldnames=header)
        writer.writeheader()

        for row in rows:
            writer.writerow(row)


def shootout():
    root = 'samples'
    for proj in sorted(os.listdir(root)):
        shootout1(root, proj)


def diffast_all(no_rr=False, use_cache=True, cache_dir=None):
    root = 'samples'
    for proj in sorted(os.listdir(root)):
        diffast_proj(root, proj, no_rr=no_rr, use_cache=use_cache, cache_dir=cache_dir)


def diffast_all_mp(no_rr=False, use_cache=True, nprocs=1, cache_dir=None):
    root = 'samples'
    for proj in sorted(os.listdir(root)):
        diffast_proj_mp(root, proj,
                        no_rr=no_rr, use_cache=use_cache, nprocs=nprocs, cache_dir=cache_dir)


def gt_all_mp(nprocs=1):
    root = 'samples'
    for proj in sorted(os.listdir(root)):
        gt_proj_mp(root, proj, nprocs=nprocs)


def gt_mp_main(use_cache=True, nprocs=1):
    mp.set_start_method('fork')
    gt_all_mp(nprocs=nprocs)


def da_mp_main(no_rr=False, use_cache=True, nprocs=1, cache_dir=None):
    mp.set_start_method('fork')
    diffast_all_mp(no_rr=no_rr, use_cache=use_cache, nprocs=nprocs, cache_dir=cache_dir)


def main(projs, samples_dir='samples', no_rr=False, use_cache=True, nprocs=1, cache_dir=None,
         run_sloccount=True, run_gumtree=True, run_diffast=True):

    if nprocs == 1:  # single process
        if run_gumtree and run_diffast:
            for proj in projs:
                shootout1(samples_dir, proj, no_rr=no_rr,
                          use_cache=use_cache, cache_dir=cache_dir)
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
                    diffast_proj(samples_dir, proj, no_rr=no_rr,
                                 use_cache=use_cache, cache_dir=cache_dir)

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
                diffast_proj_mp(samples_dir, proj, no_rr=no_rr, use_cache=use_cache,
                                nprocs=nprocs, cache_dir=cache_dir)

    # if run_sloccount and run_gumtree and run_diffast:
    #     merge_results()
    #     merge_csvs()
    #     conv_all()


def mkargparser():
    from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter

    parser = ArgumentParser(description='compare AST differencing tools',
                            formatter_class=ArgumentDefaultsHelpFormatter)

    parser.add_argument('-p', '--nprocs', dest='nprocs', type=int,
                        default=NPROCS,
                        help='specify number of processes')

    parser.add_argument('--diffast-cache-dir', dest='cache_dir', metavar='DIR',
                        default='CACHE', help='specify diffast cache dir')

    parser.add_argument('--no-rr', dest='no_rr', action='store_true',
                        help='disable rename rectification')

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


def setup_logger(log_level, log_file='shootout.log'):

    LOG_FMT = '[%(asctime)s][%(levelname)s][%(module)s][%(funcName)s]'
    LOG_FMT += ' %(message)s'

    fh = logging.FileHandler(log_file, mode='w', encoding='utf-8')
    fh.setLevel(log_level)
    fmt = logging.Formatter(LOG_FMT)
    fh.setFormatter(fmt)
    logging.basicConfig(level=log_level, handlers=[fh])
    logger.addHandler(fh)
    common.logger = logger


if __name__ == '__main__':
    parser = mkargparser()
    args = parser.parse_args()

    log_level = logging.WARNING
    if args.verbose:
        log_level = logging.INFO
    if args.debug:
        log_level = logging.DEBUG

    if not args.gumtree and not args.diffast and not args.sloccount:
        run_gumtree = True
        run_diffast = True
        run_sloccount = True
    else:
        run_gumtree = args.gumtree
        run_diffast = args.diffast
        run_sloccount = args.sloccount

    log_file = 'shootout'
    if run_sloccount:
        log_file += '.sloc'
        print('[sloccount]')
    if run_gumtree:
        log_file += '.gt'
        print('[gumtree]')
    if run_diffast:
        log_file += '.da'
        print('[diffast]')
    log_file += '.log'

    setup_logger(log_level, log_file)

    if args.nprocs < 1:
        logger.error(f'invalid number of processes: {args.nprocs}')

    main(args.projs,
         no_rr=args.no_rr, use_cache=args.use_cache, nprocs=args.nprocs, cache_dir=args.cache_dir,
         run_sloccount=run_sloccount,
         run_gumtree=run_gumtree, run_diffast=run_diffast)
