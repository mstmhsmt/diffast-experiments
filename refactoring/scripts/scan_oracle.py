#!/usr/bin/env python3

import os
import re
import json
import logging

logger = logging.getLogger()


MODIFIER_PAT = re.compile(r'private |public |protected |package ')
NEW_PAT = re.compile(r'\.new ')

RM_PAT = re.compile(r'^Rename Method (?P<mname>[^()]+)\((?P<params>[^()]*)\)( : (?P<rty>.+))? renamed to (?P<mname_>[^()]+)\((?P<params_>[^()]*)\)( : (?P<rty_>.+))? in class (?P<cfqn_>.+)$')
MARM_PAT = re.compile(r'^Move And Rename Method (?P<mname>[^()]+)\((?P<params>[^()]*)\)( : (?P<rty>.+))? in class (?P<cfqn>.+) to (?P<mname_>[^()]+)\((?P<params_>[^()]*)\)( : (?P<rty_>.+))? in class (?P<cfqn_>.+)$')
RP_PAT = re.compile(r'^Rename Parameter (?P<pname>[^:]+) : (?P<ty>.+) to (?P<pname_>[^:]+) : (?P<ty_>.+) in method (?P<mname_>[^()]+)\((?P<params_>[^()]*)\)( : (?P<rty_>.+))? in class (?P<cfqn_>.+)$')
RV_PAT = re.compile(r'^Rename Variable (?P<vname>[^:]+) : (?P<ty>.+) to (?P<vname_>[^:]+) : (?P<ty_>.+) in method (?P<mname_>[^()]+)\((?P<params_>[^()]*)\)( : (?P<rty_>.+))? in class (?P<cfqn_>.+)$')
RA_PAT = re.compile(r'^Rename Attribute (?P<fname>[^:]+) : (?P<ty>.+) to (?P<fname_>[^:]+) : (?P<ty_>.+) in class (?P<cfqn_>.+)$')
CRT_PAT = re.compile(r'Change Return Type (?P<ty>.+) to (?P<ty_>.+) in method (?P<mname_>[^()]+)\((?P<params_>[^()]*)\)( : (?P<rty_>.+))? in class (?P<cfqn_>.+)$')
CPT_PAT = re.compile(r'^Change Parameter Type (?P<pname>[^:]+) : (?P<ty>.+) to (?P<pname_>[^:]+) : (?P<ty_>.+) in method (?P<mname_>[^()]+)\((?P<params_>[^()]*)\)( : (?P<rty_>.+))? in class (?P<cfqn_>.+)$')
CVT_PAT = re.compile(r'^Change Variable Type (?P<vname>[^:]+) : (?P<ty>.+) to (?P<vname_>[^:]+) : (?P<ty_>.+) in method (?P<mname_>[^()]+)\((?P<params_>[^()]*)\)( : (?P<rty_>.+))? in class (?P<cfqn_>.+)$')
CAT_PAT = re.compile(r'^Change Attribute Type (?P<fname>[^:]+) : (?P<ty>.+) to (?P<fname_>[^:]+) : (?P<ty_>.+) in class (?P<cfqn_>.+)$')

SIG_TBL = {
    'boolean': 'Z',
    'byte': 'B',
    'char': 'C',
    'short': 'S',
    'int': 'I',
    'long': 'J',
    'float': 'F',
    'double': 'D',
    'void': 'V',
}

ARRAY_PAT = re.compile(r'^(?P<base>[^\[]+)(?P<dims>(\[\])+)$')
TY_PARAM_PAT = re.compile(r'^(?P<base>[^<]+)(?P<tparams><.+>)(?P<dims>(\[.*\])?)$')


def erase_ty_params(s):
    level = 0
    s_ = ''
    skip_flag = False
    for c in s:
        if c == '<':
            level += 1
            skip_flag = True
        elif c == '>':
            level -= 1
            if level == 0:
                skip_flag = False
        elif not skip_flag:
            s_ += c
    return s_


def get_type_sig(ty):
    if ty is None:
        return 'V'

    dims = 0
    _ty = ty

    m = TY_PARAM_PAT.match(ty)
    if m:
        _ty = TY_PARAM_PAT.sub(r'\g<base>\g<dims>', _ty)

    m = ARRAY_PAT.match(ty)
    if m:
        _ty = ARRAY_PAT.sub(r'\g<base>', _ty)
        dims = int(len(m.group('dims')) / 2)

    prefix = ''
    if dims:
        prefix = '[' * dims
    try:
        _s = SIG_TBL[_ty]
    except KeyError:
        _ty = _ty.split('.')[-1]
        _s = f'L{_ty};'

    s = prefix + _s

    return s


def abbrev(ref):
    s = ''.join([x[0] for x in ref.split(' ')])
    return s


def get_meth_sig(params, rty):
    ptys = ''
    if params:
        params_ = erase_ty_params(params)
        try:
            ptys = ''.join([get_type_sig(' '.join(p.split(' ')[1:]))
                            for p in params_.split(', ')])
        except Exception:
            pass
    rty = get_type_sig(rty)
    sig = f'({ptys}){rty}'
    return sig


def check_cfqn(cfqn):
    elems = []
    upper_flag = False
    for elem in cfqn.split('.'):
        if upper_flag and elem[0].islower():
            break
        else:
            elems.append(elem)

        if not upper_flag and elem[0].isupper():
            upper_flag = True

    cfqn_ = '.'.join(elems)
    return cfqn_


def proc_RM(desc):
    key = None
    m = RM_PAT.match(desc)
    if m:
        mname = m.group('mname')
        params = m.group('params')
        rty = m.group('rty')
        mname_ = m.group('mname_')
        params_ = m.group('params_')
        rty_ = m.group('rty_')
        cfqn_ = check_cfqn(m.group('cfqn_'))
        msig = get_meth_sig(params, rty)
        msig_ = get_meth_sig(params_, rty_)
        key = f'RM {mname}{msig}->{mname_}{msig_} {cfqn_}'
    return key


def proc_MARM(desc):
    key = None
    m = MARM_PAT.match(desc)
    if m:
        mname = m.group('mname')
        params = m.group('params')
        rty = m.group('rty')
        cfqn = check_cfqn(m.group('cfqn'))
        mname_ = m.group('mname_')
        params_ = m.group('params_')
        rty_ = m.group('rty_')
        cfqn_ = check_cfqn(m.group('cfqn_'))
        msig = get_meth_sig(params, rty)
        msig_ = get_meth_sig(params_, rty_)
        key = f'MARM {mname}{msig}:{cfqn}->{mname_}{msig_}:{cfqn_}'
    return key


def proc_RP(desc):
    key = None
    m = RP_PAT.match(desc)
    if m:
        pname = m.group('pname')
        ty = get_type_sig(m.group('ty'))
        pname_ = m.group('pname_')
        ty_ = get_type_sig(m.group('ty_'))
        mname_ = m.group('mname_')
        params_ = m.group('params_')
        rty_ = m.group('rty_')
        cfqn_ = check_cfqn(m.group('cfqn_'))
        msig_ = get_meth_sig(params_, rty_)
        key = f'RP {pname}:{ty}->{pname_}:{ty_} {mname_}{msig_} {cfqn_}'
    return key


def proc_RV(desc):
    key = None
    m = RV_PAT.match(desc)
    if m:
        vname = m.group('vname')
        ty = get_type_sig(m.group('ty'))
        vname_ = m.group('vname_')
        ty_ = get_type_sig(m.group('ty_'))
        mname_ = m.group('mname_')
        params_ = m.group('params_')
        rty_ = m.group('rty_')
        cfqn_ = check_cfqn(m.group('cfqn_'))
        msig_ = get_meth_sig(params_, rty_)
        key = f'RV {vname}:{ty}->{vname_}:{ty_} {mname_}{msig_} {cfqn_}'
    return key


def proc_RA(desc):
    key = None
    m = RA_PAT.match(desc)
    if m:
        fname = m.group('fname')
        ty = get_type_sig(m.group('ty'))
        fname_ = m.group('fname_')
        ty_ = get_type_sig(m.group('ty_'))
        cfqn_ = check_cfqn(m.group('cfqn_'))
        key = f'RA {fname}:{ty}->{fname_}:{ty_} {cfqn_}'
    return key


def proc_CRT(desc):
    key = None
    m = CRT_PAT.match(desc)
    if m:
        ty = get_type_sig(m.group('ty'))
        ty_ = get_type_sig(m.group('ty_'))
        mname_ = m.group('mname_')
        params_ = m.group('params_')
        rty_ = m.group('rty_')
        cfqn_ = check_cfqn(m.group('cfqn_'))
        msig_ = get_meth_sig(params_, rty_)
        key = f'CRT {ty}->{ty_} {mname_}{msig_} {cfqn_}'
    return key


def proc_CPT(desc):
    key = None
    m = CPT_PAT.match(desc)
    if m:
        pname = m.group('pname')
        ty = get_type_sig(m.group('ty'))
        pname_ = m.group('pname_')
        ty_ = get_type_sig(m.group('ty_'))
        mname_ = m.group('mname_')
        params_ = m.group('params_')
        rty_ = m.group('rty_')
        cfqn_ = check_cfqn(m.group('cfqn_'))
        msig_ = get_meth_sig(params_, rty_)
        key = f'CPT {pname}:{ty}->{pname_}:{ty_} {mname_}{msig_} {cfqn_}'
    return key


def proc_CVT(desc):
    d = None
    m = CVT_PAT.match(desc)
    if m:
        vname = m.group('vname')
        ty = get_type_sig(m.group('ty'))
        vname_ = m.group('vname_')
        ty_ = get_type_sig(m.group('ty_'))
        mname_ = m.group('mname_')
        params_ = m.group('params_')
        rty_ = m.group('rty_')
        cfqn_ = check_cfqn(m.group('cfqn_'))
        msig_ = get_meth_sig(params_, rty_)
        d = f'CVT {vname}:{ty}->{vname_}:{ty_} {mname_}{msig_} {cfqn_}'
    return d


def proc_CAT(desc):
    d = None
    m = CAT_PAT.match(desc)
    if m:
        fname = m.group('fname')
        ty = get_type_sig(m.group('ty'))
        fname_ = m.group('fname_')
        ty_ = get_type_sig(m.group('ty_'))
        cfqn_ = check_cfqn(m.group('cfqn_'))
        d = f'CAT {fname}:{ty}->{fname_}:{ty_} {cfqn_}'
    return d


PROC_TBL = {
    'Rename Method': proc_RM,
    # 'Move And Rename Method': proc_MARM,
    'Rename Parameter': proc_RP,
    'Rename Variable': proc_RV,
    'Rename Attribute': proc_RA,
    'Change Return Type': proc_CRT,
    'Change Parameter Type': proc_CPT,
    'Change Variable Type': proc_CVT,
    'Change Attribute Type': proc_CAT,
}

target_refactorings = list(PROC_TBL.keys())


def purify_desc(desc):
    desc0 = MODIFIER_PAT.sub('', desc)
    desc1 = NEW_PAT.sub('.', desc0)
    desc2 = desc1.replace('...', '[]')
    return desc2


def scan_deleted_commits(path):
    tbl = {}
    try:
        with open(path) as f:
            for line in f.readlines():
                url = line.strip()
                elems = url.split('/')
                commit = elems[-1]
                proj_id = '/'.join(elems[-4:-2])
                try:
                    tbl[proj_id].append(commit)
                except KeyError:
                    tbl[proj_id] = [commit]
    except Exception:
        pass
    return tbl


def scan_oracle(oracle_path, out_path=None):
    data = {}  # proj_id -> cid -> refty -> validation -> key_list

    deleted_commits_file = os.path.join(os.path.dirname(oracle_path),
                                        'deleted_commits.txt')

    deleted_commits_tbl = scan_deleted_commits(deleted_commits_file)

    logger.info('loading "{}"...'.format(os.path.abspath(oracle_path)))
    with open(oracle_path, 'r') as f:

        for commit in json.load(f):
            repo_url = commit['repository']
            refs = commit['refactorings']
            sha1 = commit['sha1']

            user_name, _repo_name = repo_url.split('/')[-2:]
            repo_name = '.'.join(_repo_name.split('.')[0:-1])
            proj_id = f"{user_name}/{repo_name}"
            cid = sha1[0:7]

            if sha1 in deleted_commits_tbl.get(proj_id, []):
                continue

            try:
                cid_tbl = data[proj_id]
            except KeyError:
                cid_tbl = {}
                data[proj_id] = cid_tbl
            try:
                rtbl = cid_tbl[cid]
            except KeyError:
                rtbl = {}
                cid_tbl[cid] = rtbl

            for ref in refs:
                refty = ref['type']

                if refty in target_refactorings:
                    _refty = abbrev(refty)
                    try:
                        vtbl = rtbl[_refty]
                    except KeyError:
                        vtbl = {}
                        rtbl[_refty] = vtbl

                    orig_desc = ref['description']
                    validation = ref['validation']

                    try:
                        keyl = vtbl[validation]
                    except KeyError:
                        keyl = []
                        vtbl[validation] = keyl

                    desc = purify_desc(orig_desc)
                    key = (PROC_TBL[refty](desc), orig_desc)

                    # print(orig_desc)
                    if key is None:
                        logger.warning(f'failed to proc: {orig_desc}')
                        logger.warning(f'desc: {desc}')
                        logger.warning(f'at {repo_url}')
                    else:
                        # print(f'{key}')
                        keyl.append(key)

    pids = set()
    cids = set()
    nkeys = 0
    for pid, ctbl in data.items():
        pids.add(pid)
        for cid, rtbl in ctbl.items():
            cids.add(cid)
            for r, vtbl in rtbl.items():
                for v, kl in vtbl.items():
                    nkeys += len(kl)
    logger.info('{} keys from {} commits from {} projects found'
                .format(nkeys, len(cids), len(pids)))

    if out_path:
        logger.info('dumping into "%s"...' % os.path.abspath(out_path))
        with open(out_path, 'w') as f:
            json.dump(data, f)

    return data


def main():
    from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter

    parser = ArgumentParser(description='scan Refactoring Oracle',
                            formatter_class=ArgumentDefaultsHelpFormatter)

    parser.add_argument('--oracle', type=str, default='data.json',
                        help='Oracle "data.json"')

    parser.add_argument('-o', '--outfile', type=str, dest='outfile',
                        default=None)

    args = parser.parse_args()

    scan_oracle(args.oracle, args.outfile)


if __name__ == '__main__':
    pass
