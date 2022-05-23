#!/usr/bin/env python3

import os

CCA_HOME = os.getenv('CCA_HOME', '/opt/cca')
VAR_DIR = os.getenv('CCA_VAR_DIR', '/var/lib/cca')
LOG_DIR = os.getenv('CCA_LOG_DIR', '/var/log/cca')

VIRTUOSO_PW = 'rrj'
VIRTUOSO_PORT = 1111

#

ONT_DIR = os.path.join(CCA_HOME, 'ontologies')

FB_DIR = os.path.join(VAR_DIR, 'db')
FACT_DIR = os.path.join(VAR_DIR, 'fact')
WORK_DIR = os.path.join(VAR_DIR, 'work')

REFACT_DIR = os.path.join(VAR_DIR, 'refactoring')

if __name__ == '__main__':
    print(f'VAR_DIR: {VAR_DIR}')
    print(f'fACT_DIR: {FACT_DIR}')
    print(f'LOG_DIR: {LOG_DIR}')
    print(f'FB_DIR: {FB_DIR}')
    print(f'ONT_DIR: {ONT_DIR}')
    print(f'WORK_DIR: {WORK_DIR}')
    print(f'REFACT_DIR: {REFACT_DIR}')
    print(f'VIRTUOSO_PW: {VIRTUOSO_PW}')
    print(f'VIRTUOSO_PORT: {VIRTUOSO_PORT}')
