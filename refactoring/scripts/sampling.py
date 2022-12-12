#!/usr/bin/env python3

import os
import json
import random
import tarfile
import http.client
import urllib.parse
# import traceback
import logging

import pygit2
import github
import requests
# import rapidjson as json

logger = logging.getLogger()

GITHUB_API_TOKEN = 'SET YOUR OWN'

CACHE_JSON = 'cache.json'

EXTS = ['.java']


def issrc(name):
    b = False
    if name:
        for ext in EXTS:
            if name.endswith(ext):
                b = True
                break
            else:
                cap = ext.upper()
                if name.endswith(cap):
                    b = True
                    break
    return b


def get_modified_files(_commit, commit):
    delta = _commit.tree.diff_to_tree(commit.tree)
    modified = []
    for p in delta:
        old_file = p.delta.old_file
        new_file = p.delta.new_file
        if issrc(old_file.path) or issrc(new_file.path):
            modified.append((old_file, new_file))
    return modified


def save_file(repo, fobj, dpath):
    blob = repo.get(fobj.id, None)
    if blob:
        fpath = os.path.join(dpath, fobj.path)
        d = os.path.dirname(fpath)
        if not os.path.exists(d):
            os.makedirs(d)
        with open(fpath, 'wb') as f:
            f.write(blob.data)
            logger.debug(f'file saved at "{fpath}"')


def check_url(url):
    o = urllib.parse.urlparse(url)
    conn = http.client.HTTPSConnection(o.netloc)
    conn.request('GET', o.path)
    res = conn.getresponse()
    b = res.status != 404
    return b


def sampling(json_file, nsamples, refactoring=None, out='a.json'):
    res = []
    ref_list = []
    failure_count = 0

    if os.path.exists(CACHE_JSON):
        with open(CACHE_JSON, 'r') as f:
            ref_list = json.load(f)
    else:
        with open(json_file) as f:
            data = json.load(f)
            for commit in data:
                # oid = commit['id']
                repo = commit['repository']
                sha1 = commit['sha1']
                url = commit['url']
                if check_url(url):
                    for ref in commit['refactorings']:
                        valid = ref['validation'] == 'TP'
                        if valid:
                            refty = ref['type']
                            if refactoring is None or refactoring == refty:
                                desc = ref['description']
                                d = {'repo': repo, 'sha1': sha1,
                                     'type': refty, 'desc': desc}
                                ref_list.append(d)
                else:
                    failure_count += 1
                    logger.warning(f'{url}: failed to access')

            if failure_count:
                logger.warning(f'failed to get {failure_count} commits')

            if ref_list:
                with open(CACHE_JSON, 'w') as f:
                    json.dump(ref_list, f)

    if nsamples > 0 and len(ref_list) > nsamples:
        res = random.sample(ref_list, k=nsamples)
    else:
        res = ref_list

    if res:
        with open(out, 'w') as f:
            json.dump(res, f)

    return res


def gh_dl(dl_link, out_path):
    logger.info(f'downloading {dl_link}...')
    resp = requests.get(dl_link)
    dir_path = os.path.dirname(out_path)
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)
    with open(out_path, 'wb') as f:
        f.write(resp.content)
    logger.info(f'downloaded to {out_path}')


def clone_repos(repo_tbl, repo_dir, sample_dir, modified_only=False):

    for repo_url, cl in repo_tbl.items():
        logger.info(f'repo_url={repo_url}')

        user_name, repo_name = repo_url.split('/')[-2:]

        if repo_name.endswith('.git'):
            repo_name = repo_name[:-4]

        repo_path = os.path.join(repo_dir, user_name, repo_name)

        if not os.path.exists(repo_path):
            logger.info(f'cloning {repo_url} into {repo_path}...')
            pygit2.clone_repository(repo_url, repo_path, bare=True)

        sample_path = os.path.join(sample_dir, user_name, repo_name)

        repo = pygit2.Repository(repo_path)

        for c in cl:
            logger.info(f'commit={c}')

            short_id = c[:7]

            before_path = os.path.join(sample_path, f'{short_id}-before')
            after_path = os.path.join(sample_path,  f'{short_id}-after')

            if os.path.exists(before_path) and os.path.exists(after_path):
                continue

            before_tar_path = before_path + '.tar'
            after_tar_path = after_path + '.tar'

            before_tgz_path = before_tar_path + '.gz'
            after_tgz_path = after_tar_path + '.gz'

            pdir = os.path.dirname(after_path)
            if not os.path.exists(pdir):
                os.makedirs(pdir)

            commit_id = pygit2.Oid(hex=c)
            commit = None
            _commit = None

            gh_flag = False

            try:
                commit = repo[commit_id]
                _commit = commit.parents[0]
                logger.info('tree={}'.format(str(commit.tree.id)))
                logger.info('tree_={}'.format(str(_commit.tree.id)))
            except Exception:
                logger.warning(f'"{c}": not found')
                try:
                    gh = github.MainClass.Github(GITHUB_API_TOKEN)
                    logger.warning('finding via GitHub API...')
                    gh_repo = gh.get_repo(f'{user_name}/{repo_name}')
                    dl_link_after = gh_repo.get_archive_link('tarball', c)
                    logger.info(f'dl_link_after={dl_link_after}')
                    dl_link_before = gh_repo.get_archive_link('tarball', c+'^')
                    logger.info(f'dl_link_before={dl_link_before}')
                    gh_flag = True
                except Exception as e:
                    logger.warning(f'failed to get download link: {e}')
                    continue

            if modified_only:
                if gh_flag:
                    try:
                        commit = gh_repo.get_commit(c)
                        _commit = commit.parents[0]
                        logger.info('{} modified files found'
                                    .format(len(commit.files)))
                        for f in commit.files:
                            fn = f.filename
                            logger.info(f'fn={fn}')
                            if fn.endswith('.java') and f.status == 'modified':
                                fp = os.path.join(after_path, fn)
                                fc = gh_repo.get_contents(fn, commit.sha)
                                gh_dl(fc.download_url, fp)
                                _fn = fn
                                if f.previous_filename:
                                    _fn = f.previous_filename
                                _fc = gh_repo.get_contents(_fn, _commit.sha)
                                _fp = os.path.join(before_path, _fn)
                                gh_dl(_fc.download_url, _fp)
                    except Exception as e:
                        logger.warning(f'failed to handle {c}: {e}')
                        continue

                else:
                    modified = get_modified_files(_commit, commit)
                    logger.info('{} modified source files found'
                                .format(len(modified)))
                    for fobj0, fobj1 in modified:
                        save_file(repo, fobj0, before_path)
                        save_file(repo, fobj1, after_path)

            elif gh_flag:
                try:
                    gh_dl(dl_link_before, before_tgz_path)
                except Exception:
                    logger.warning(f'failed to download {dl_link_before}')
                    continue
                try:
                    gh_dl(dl_link_after, after_tgz_path)
                except Exception:
                    logger.warning(f'failed to download {dl_link_after}')
                    continue

                with tarfile.open(after_tgz_path, 'r') as a:
                    def is_within_directory(directory, target):
                        
                        abs_directory = os.path.abspath(directory)
                        abs_target = os.path.abspath(target)
                    
                        prefix = os.path.commonprefix([abs_directory, abs_target])
                        
                        return prefix == abs_directory
                    
                    def safe_extract(tar, path=".", members=None, *, numeric_owner=False):
                    
                        for member in tar.getmembers():
                            member_path = os.path.join(path, member.name)
                            if not is_within_directory(path, member_path):
                                raise Exception("Attempted Path Traversal in Tar File")
                    
                        tar.extractall(path, members, numeric_owner=numeric_owner) 
                        
                    
                    safe_extract(a, after_path)
                os.remove(after_tgz_path)

                with tarfile.open(before_tgz_path, 'r') as a:
                    def is_within_directory(directory, target):
                        
                        abs_directory = os.path.abspath(directory)
                        abs_target = os.path.abspath(target)
                    
                        prefix = os.path.commonprefix([abs_directory, abs_target])
                        
                        return prefix == abs_directory
                    
                    def safe_extract(tar, path=".", members=None, *, numeric_owner=False):
                    
                        for member in tar.getmembers():
                            member_path = os.path.join(path, member.name)
                            if not is_within_directory(path, member_path):
                                raise Exception("Attempted Path Traversal in Tar File")
                    
                        tar.extractall(path, members, numeric_owner=numeric_owner) 
                        
                    
                    safe_extract(a, before_path)
                os.remove(before_tgz_path)

            else:
                with tarfile.open(after_tar_path, 'w') as a:
                    logger.info(f'  {c} --> {after_path}')
                    try:
                        repo.write_archive(commit, a)
                    except Exception:
                        logger.warning(f'failed to checkout {c}')
                        try:
                            gh = github.MainClass.Github(GITHUB_API_TOKEN)
                            gh_repo = gh.get_repo(f'{user_name}/{repo_name}')
                            dl_link_after = gh_repo.get_archive_link('tarball', c)
                            logger.info(f'dl_link_after={dl_link_after}')
                            gh_dl(dl_link_after, after_tgz_path)
                            after_tar_path = after_tgz_path
                        except Exception:
                            continue

                with tarfile.open(after_tar_path, 'r') as a:
                    def is_within_directory(directory, target):
                        
                        abs_directory = os.path.abspath(directory)
                        abs_target = os.path.abspath(target)
                    
                        prefix = os.path.commonprefix([abs_directory, abs_target])
                        
                        return prefix == abs_directory
                    
                    def safe_extract(tar, path=".", members=None, *, numeric_owner=False):
                    
                        for member in tar.getmembers():
                            member_path = os.path.join(path, member.name)
                            if not is_within_directory(path, member_path):
                                raise Exception("Attempted Path Traversal in Tar File")
                    
                        tar.extractall(path, members, numeric_owner=numeric_owner) 
                        
                    
                    safe_extract(a, after_path)
                os.remove(after_tar_path)

                with tarfile.open(before_tar_path, 'w') as a:
                    _c = str(_commit.id)
                    logger.info(f'  {_c} --> {before_path}')
                    try:
                        repo.write_archive(_commit, a)
                    except Exception:
                        logger.warning(f'failed to checkout {_c}')
                        try:
                            gh = github.MainClass.Github(GITHUB_API_TOKEN)
                            gh_repo = gh.get_repo(f'{user_name}/{repo_name}')
                            dl_link_before = gh_repo.get_archive_link('tarball', c+'^')
                            logger.info(f'dl_link_before={dl_link_before}')
                            gh_dl(dl_link_before, before_tgz_path)
                            before_tar_path = before_tgz_path
                        except Exception:
                            continue

                with tarfile.open(before_tar_path, 'r') as a:
                    def is_within_directory(directory, target):
                        
                        abs_directory = os.path.abspath(directory)
                        abs_target = os.path.abspath(target)
                    
                        prefix = os.path.commonprefix([abs_directory, abs_target])
                        
                        return prefix == abs_directory
                    
                    def safe_extract(tar, path=".", members=None, *, numeric_owner=False):
                    
                        for member in tar.getmembers():
                            member_path = os.path.join(path, member.name)
                            if not is_within_directory(path, member_path):
                                raise Exception("Attempted Path Traversal in Tar File")
                    
                        tar.extractall(path, members, numeric_owner=numeric_owner) 
                        
                    
                    safe_extract(a, before_path)
                os.remove(before_tar_path)


def clone_repos_from_data(data, repo_dir, sample_dir, modified_only=False):
    repo_tbl = {}
    for d in data:
        repo_url = d['repo']
        sha1 = d['sha1']
        try:
            cl = repo_tbl[repo_url]
        except KeyError:
            cl = []
            repo_tbl[repo_url] = cl

        if sha1 not in cl:
            cl.append(sha1)

    clone_repos(repo_tbl, repo_dir, sample_dir, modified_only=modified_only)


if __name__ == '__main__':
    from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter

    parser = ArgumentParser(description='sampling from Refactoring Oracle',
                            formatter_class=ArgumentDefaultsHelpFormatter)

    parser.add_argument('--oracle', type=str, default='data.json',
                        help='specify Oracle')

    parser.add_argument('-n', '--nsamples', type=int, default=10,
                        help='specify number of samples')

    parser.add_argument('-d', '--debug', dest='debug', action='store_true',
                        help='enable debug printing')

    parser.add_argument('-r', '--refactoring', dest='ref', default=None,
                        help='specify refactoring type')

    parser.add_argument('-o', '--out-json', dest='out_json', default='a.json',
                        help='specify output JSON file')

    parser.add_argument('-s', '--sampled-json', dest='in_json', default=None,
                        help='specify sampled refactorings')

    parser.add_argument('-m', '--modified-only', dest='modified_only',
                        action='store_true',
                        help='checkout modified source files only')

    args = parser.parse_args()

    log_level = logging.INFO
    if args.debug:
        log_level = logging.DEBUG
    fh = logging.FileHandler('sampling.log', mode='w', encoding='utf-8')
    fh.setLevel(log_level)
    fmt = logging.Formatter('[%(asctime)s][%(levelname)s] %(message)s')
    fh.setFormatter(fmt)
    logging.basicConfig(level=log_level, handlers=[fh])
    logger.addHandler(fh)

    data = None

    if args.in_json is None:

        if os.path.exists(args.out_json):
            print('"{}" exists!'.format(args.out_json))
            while True:
                a = input('Do you want to overwrite? [y/n] ')
                if a == 'y':
                    break
                elif a == 'n':
                    exit(0)

        if args.nsamples <= 0:
            logger.info('extracting {} samples from "{}"...'
                        .format(args.ref if args.ref else 'arbitrary',
                                args.oracle))
        else:
            logger.info('sampling {} {} samples from "{}"...'
                        .format(args.nsamples,
                                args.ref if args.ref else 'arbitrary',
                                args.oracle))

        data = sampling(args.oracle, args.nsamples, refactoring=args.ref,
                        out=args.out_json)

        logger.info('result dumped into "{}"'.format(args.out_json))

    else:
        with open(args.in_json) as f:
            data = json.load(f)

    clone_repos_from_data(data, 'repositories', 'samples',
                          modified_only=args.modified_only)
