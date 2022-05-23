#!/usr/bin/env python3

import json
import re

FROM_CLASS_PAT = re.compile(r'from class')
COMMA_NON_SPACE_PAT = re.compile(r',(?P<c>\S)')

if __name__ == '__main__':
    json_file = 'data.json'
    out_file = '_data.json'

    print(f'reading {json_file}')
    with open(json_file) as f:
        data = json.load(f)
        for commit in data:
            ref_list = []
            for ref in commit['refactorings']:
                refty = ref['type']
                desc = ref['description']

                if not desc.startswith(refty):
                    print(f'malformed instance: [{refty}] {desc}')
                    continue

                desc0 = FROM_CLASS_PAT.sub('in class', desc)
                desc1 = COMMA_NON_SPACE_PAT.sub(r', \g<c>', desc0)
                if desc1 != desc:
                    ref['description'] = desc1

                ref_list.append(ref)

            commit['refactorings'] = ref_list

    print(f'writing {out_file}')
    with open(out_file, 'w') as f:
        json.dump(data, f)
