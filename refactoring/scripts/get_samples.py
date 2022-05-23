#!/usr/bin/env python3

import re
import logging

from sampling import clone_repos

logger = logging.getLogger()

COMMIT_URL_PAT = re.compile(r'^https://github.com/(?P<user>[^/]+)/(?P<repo>[^/]+)/commit/(?P<sha1>[0-9a-f]+).*$')


def get(commit_list_file):
    tbl = {}
    with open(commit_list_file) as f:
        for _line in f.readlines():
            line = _line.rstrip()
            m = COMMIT_URL_PAT.match(line)
            if m:
                user = m.group('user')
                repo = m.group('repo')
                sha1 = m.group('sha1')
                repo_url = f'https://github.com/{user}/{repo}.git'
                try:
                    sl = tbl[repo_url]
                except KeyError:
                    sl = []
                    tbl[repo_url] = sl
                sl.append(sha1)
    return tbl


if __name__ == '__main__':
    from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter

    parser = ArgumentParser(description='get samples GitHub commits',
                            formatter_class=ArgumentDefaultsHelpFormatter)

    parser.add_argument('commit_list', type=str)

    parser.add_argument('-d', '--debug', dest='debug', action='store_true',
                        help='enable debug printing')

    parser.add_argument('-m', '--modified-only', dest='modified_only',
                        action='store_true',
                        help='checkout modified source files only')

    args = parser.parse_args()

    log_level = logging.INFO
    if args.debug:
        log_level = logging.DEBUG

    logging.basicConfig(format='[%(asctime)s][%(levelname)s] %(message)s',
                        level=log_level)

    repo_tbl = get(args.commit_list)

    clone_repos(repo_tbl, 'repositories', 'samples',
                modified_only=args.modified_only)
