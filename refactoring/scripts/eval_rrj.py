#!/usr/bin/env python3

import os
import json
import math
import logging

from scan_oracle import scan_oracle
from common import REFACT_DIR

logger = logging.getLogger()


DEFAULT_TARGET_REF = 'RM:RP:RV:RA:CRT:CPT:CVT:CAT'
TARGET_REF_LIST = DEFAULT_TARGET_REF.split(':')


def eval_rrj(oracle_path, ref_dir=REFACT_DIR, target_refs=TARGET_REF_LIST):

    if not os.path.exists(oracle_path):
        logger.error(f'not found: "{oracle_path}"')
        return

    if not os.path.exists(ref_dir):
        logger.error(f'not found: "{ref_dir}"')
        return

    rrj_result = {}  # proj_id -> cid -> refty -> keyl

    for uname in os.listdir(ref_dir):
        for rname in os.listdir(os.path.join(ref_dir, uname)):
            if rname.endswith('.tdata') or rname.endswith('.json'):
                continue

            proj_id = f'{uname}/{rname}'
            logger.info(f'proj_id={proj_id}')
            ref_keys_path = os.path.join(ref_dir, proj_id, 'ref_keys.json')
            logger.info(f'loading "{ref_keys_path}"...')
            try:
                with open(ref_keys_path) as f:
                    rrj_result[proj_id] = json.load(f)
            except Exception:
                logger.error(f'failed to load "{ref_keys_path}"')
                continue

    #

    oracle = scan_oracle(oracle_path, out_path='oracle.json')

    ref_tbl = {}

    missed_key_tbl = {}  # proj_id -> ref -> key set

    for proj_id, ctbl in oracle.items():

        try:
            rmtbl = missed_key_tbl[proj_id]
        except KeyError:
            rmtbl = {}
            missed_key_tbl[proj_id] = rmtbl

        for cid, oracle_rtbl in ctbl.items():

            rtbl = rrj_result.get(proj_id, {}).get(cid, {})

            for ref, oracle_vtbl in oracle_rtbl.items():

                rrj_keyl = rtbl.get(ref, [])
                rrj_keys = set(rrj_keyl)

                tp_keyl = [tuple(x) for x in oracle_vtbl.get('TP', [])]
                ctp_keyl = [tuple(x) for x in oracle_vtbl.get('CTP', [])]
                fp_keyl = [tuple(x) for x in oracle_vtbl.get('FP', [])]

                tp_keys = set(tp_keyl)
                ctp_keys = set(ctp_keyl)

                _tp_keys = set([x[0] for x in tp_keyl])
                _ctp_keys = set([x[0] for x in ctp_keyl])
                _fp_keys = set([x[0] for x in fp_keyl])

                # if not rrj_keys and (tp_keys | ctp_keys):
                #     print(f'!!!!! {proj_id} {cid} {ref}')

                _atp_keys = _tp_keys | _ctp_keys

                rrj_tp_keyl = []
                for k in rrj_keyl:
                    if k in _atp_keys:
                        rrj_tp_keyl.append(k)

                rrj_ukn_keys = rrj_keys - set(rrj_tp_keyl) - _fp_keys

                _mks = _atp_keys - rrj_keys
                if _mks:
                    __mks = set()
                    for k in _mks:
                        __mks.add(k + f' {cid}')

                    try:
                        mks = rmtbl[ref]
                    except KeyError:
                        mks = set()
                        rmtbl[ref] = mks
                    mks |= __mks

                ntp = len(rrj_tp_keyl)
                np = len(rrj_keyl)
                natp = len(tp_keys | ctp_keys)
                nukn = len(rrj_ukn_keys)

                try:
                    tbl = ref_tbl[ref]
                    tbl['ntp'] += ntp
                    tbl['np'] += np
                    tbl['natp'] += natp
                    tbl['nukn'] += nukn
                except KeyError:
                    tbl = {'ntp': ntp, 'np': np, 'natp': natp,
                           'nukn': nukn}
                    ref_tbl[ref] = tbl

    to_be_removed = set()
    for proj_id, rmtbl in missed_key_tbl.items():
        if not rmtbl:
            to_be_removed.add(proj_id)
    for proj_id in to_be_removed:
        del(missed_key_tbl[proj_id])

    print('missed keys:')
    for proj_id, rmtbl in missed_key_tbl.items():
        print(f'********** {proj_id} **********')
        for ref, mks in rmtbl.items():
            for mk in mks:
                print(f'{mk}')

    total_ntp = 0
    total_np = 0
    total_natp = 0
    total_nukn = 0

    print('Ref   TP    P  ATP  Ukn Recall   Prec')
    for ref in ('RM', 'RV', 'RP', 'RA', 'CRT', 'CVT', 'CPT', 'CAT'):
        tbl = ref_tbl[ref]

        ntp = tbl['ntp']
        np = tbl['np']
        natp = tbl['natp']
        nukn = tbl['nukn']
        if np == 0:
            prec = (math.nan, math.nan)
        else:
            prec = (ntp / np, (ntp + nukn) / np)
        if natp == 0:
            recall = math.nan
        else:
            recall = ntp / natp
        print(f'{ref:3s} {ntp:4d} {np:4d} {natp:4d} {nukn:4d}   {recall:4.2f} {prec[0]:4.2f}-{prec[1]:4.2f}')
        total_ntp += ntp
        total_np += np
        total_natp += natp
        total_nukn += nukn

    if total_np == 0:
        prec = (math.nan, math.nan)
    else:
        prec = (total_ntp / total_np, (total_ntp + total_nukn) / total_np)
    if total_natp == 0:
        recall = math.nan
    else:
        recall = total_ntp / total_natp

    print('Total')
    print(f'TP: {total_ntp}')
    print(f'P:  {total_np}')
    print(f'ATP: {total_natp}')
    print(f'PREC:   {prec[0]:4.2f}-{prec[1]:4.2f}')
    print(f'RECALL: {recall:4.2f}')


def main():
    from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter

    parser = ArgumentParser(description='evaluate RRJ result',
                            formatter_class=ArgumentDefaultsHelpFormatter)

    parser.add_argument('--oracle', type=str, default='data.json',
                        help='Oracle "data.json"')

    parser.add_argument('--rrj-ref-dir', type=str, default=REFACT_DIR,
                        help='RRJ refactoring result dir')

    parser.add_argument('-t', '--targets', dest='targets', type=str,
                        default=DEFAULT_TARGET_REF,
                        help='target refactoring patters')

    args = parser.parse_args()

    targets = args.targets.split(':')

    eval_rrj(args.oracle, args.rrj_ref_dir, target_refs=targets)


if __name__ == '__main__':
    main()
