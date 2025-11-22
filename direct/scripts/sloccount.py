#!/usr/bin/env python3

# A sloccount driver

import os
import re
import tempfile
import logging

from subprocess import Popen, PIPE

logger = logging.getLogger()

###

SLOCCOUNT = 'sloccount'

HEAD = 'Totals grouped by language'

PAT = re.compile(r'\b(?P<lang>\w+)\s*:\s*(?P<sloc>\d+)', re.I)

LANG_TBL = {
    'c': ['ansic'],
    'fortran': ['fortran', 'f90'],
}

###


def escape(s):
    if '$' in s:
        s = s.replace('$', r'\$')
    return s


def unescape(s):
    if r'\$' in s:
        s = s.replace(r'\$', '$')
    return s


class PopenContext(object):
    def __init__(self, cmd, rc_check=True):
        self.cmd = cmd
        self.rc_check = rc_check

    def __enter__(self):
        self._po = Popen(self.cmd,
                         shell=True,
                         stdout=PIPE,
                         stderr=PIPE,
                         close_fds=True,
                         universal_newlines=True)
        return self._po

    def __exit__(self, *exc_info):
        (exc, v, tr) = exc_info

        if exc == OSError:
            logger.error(f'execution failed: {v}')
            return True

        elif exc is None:
            rc = self._po.returncode
            if rc and self.rc_check:
                if rc != 0:
                    logger.warning(f'"{self.cmd}":'
                                   f' terminated abnormally (exitcode={rc})')
            return True

        else:
            return False


def get_langs(lang):
    ll = [lang]
    try:
        ll = LANG_TBL[lang]
    except KeyError:
        pass
    return ll


def sloccount(path, datadir=None):
    opts = ' --follow --autogen'
    if datadir:
        opts += f' --datadir {datadir}'
        if not os.path.exists(datadir):
            os.makedirs(datadir)

    path = escape(path)

    cmd = f'{SLOCCOUNT}{opts} "{path}"'
    logger.debug(f'cmd="{cmd}"')

    c = PopenContext(cmd)
    total_sloc = 0
    sloc_tbl = {}
    with c as p:
        (o, e) = p.communicate()
        flag = False
        for _line in o.split('\n'):
            line = _line.strip()
            logger.debug(f'line="{line}"')

            if flag:
                m = PAT.search(line)
                if m:
                    try:
                        lang = m.group('lang')
                        logger.debug(f'LANG="{lang}"')
                        sloc = int(m.group('sloc'))
                        logger.debug(f'SLOC="{sloc}"')
                        total_sloc += sloc

                        try:
                            sloc_tbl[lang] += sloc
                        except KeyError:
                            sloc_tbl[lang] = sloc

                    except Exception as exc:
                        logger.warning(f'{exc}')
                else:
                    flag = False
                    logger.debug('END')

            if line.startswith(HEAD):
                flag = True
                logger.debug('BEGIN')

    return {'tbl': sloc_tbl, 'total': total_sloc}


def sloccount_str(content):
    (fd, tmp) = tempfile.mkstemp()
    os.close(fd)

    f = open(tmp, 'w')
    f.write(content)
    f.close()

    sloc = sloccount(tmp)

    os.unlink(tmp)

    return sloc


def sloccount_for_lang(lang, path, datadir=None):
    ll = get_langs(lang)
    logger.debug(f'lang="{lang}" ({",".join(ll)})')
    r = sloccount(path, datadir=datadir)
    count = 0
    for lang in ll:
        count += r['tbl'].get(lang, 0)

    return count


if __name__ == '__main__':
    from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter

    parser = ArgumentParser(description='SLOCCount Driver',
                            formatter_class=ArgumentDefaultsHelpFormatter)

    parser.add_argument('path', type=str, help='directory or file to be read')

    parser.add_argument('-l', '--lang', dest='lang', type=str, default=None,
                        help='programming language to be handled')

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
    logging.basicConfig(format='[%(levelname)s][%(funcName)s] %(message)s',
                        level=log_level)

    if args.lang:
        c = sloccount_for_lang(args.lang, args.path)
        print(f'{c}')

    else:
        sloc = sloccount(args.path)

        for x in sloc['tbl'].items():
            print('{}: {}'.format(*x))

        print(f'total: {sloc["total"]}')
