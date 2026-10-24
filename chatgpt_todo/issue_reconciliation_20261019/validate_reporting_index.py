#!/usr/bin/env python3
"""Validate the *reporting* index, not claims or live GitHub issue resolution.

Exit 0: all declared rows have syntactically valid issue/report bindings.
Exit 1: incomplete/malformed declared reporting index. No publication authority.
Readback of GitHub writes is separately recorded; offline checks cannot prove it.
"""
from pathlib import Path
import csv
import json
import re
import sys

HERE = Path(__file__).resolve().parent
EXPECTED = 55  # frozen enumerated reporting scope, not all repository findings
ALLOWED_ISSUES = {1045, 1592, 1598, 1603, 1607, 1608, 1611, 1616, *range(1630, 1637)}
REQUIRED = {'finding_id','issue_number','report_url','evidence_kind','description','source_aliases','resolution_state'}
KINDS = {'AUDIT_QUALIFICATION','CONFIRMED_SOURCE_OR_SYNTHETIC_DEFECT','EXTERNAL_REFERENCE_GAP','MEASURAND_OR_INFERENCE_GAP','POSITIVE_CONTROL','STATIC_PENDING'}


def validate(path: Path) -> dict:
    with path.open(newline='', encoding='utf-8') as handle:
        raw = list(csv.reader(handle, strict=True))
    if not raw or set(raw[0]) != REQUIRED or len(raw[0]) != len(REQUIRED):
        raise ValueError('wrong/duplicate header')
    ids, aliases, issues = set(), set(), set()
    for number, values in enumerate(raw[1:], 2):
        if len(values) != len(raw[0]):
            raise ValueError(f'row {number}: width mismatch')
        row = dict(zip(raw[0], values, strict=True))
        if any(not v.strip() for v in row.values()):
            raise ValueError(f'row {number}: missing binding')
        ident = row['finding_id']
        if ident in ids:
            raise ValueError('duplicate finding ID: '+ident)
        ids.add(ident)
        issue = int(row['issue_number'])
        if issue not in ALLOWED_ISSUES:
            raise ValueError('unrecognized issue in frozen reporting scope')
        url = f'https://github.com/SzeChunYiu/ccb-testbeam/issues/{issue}'
        if not re.fullmatch(re.escape(url)+r'(?:#issuecomment-[1-9][0-9]*)?', row['report_url']):
            raise ValueError('report link disagrees with issue')
        if row['evidence_kind'] not in KINDS:
            raise ValueError('unknown evidence class')
        for alias in row['source_aliases'].split(';'):
            if ':' not in alias or alias in aliases:
                raise ValueError('unscoped/duplicate source alias')
            aliases.add(alias)
        issues.add(issue)
    if len(ids) != EXPECTED:
        raise ValueError('declared reporting coverage incomplete')
    return {'reporting_scope_rows':len(ids),'source_aliases':len(aliases),
            'distinct_issue_owners':len(issues),'issue_numbers':sorted(issues),
            'unbound_rows':0,'scientific_release':'NOT_AUTHORIZED',
            'live_issue_readback_performed_by_this_script':False,
            'whole_repository_inventory_complete':False}


if __name__ == '__main__':
    try:
        result = validate(HERE/'FINDING_ISSUE_INDEX.csv')
    except (OSError, ValueError, csv.Error) as exc:
        print(json.dumps({'status':'REPORTING_INDEX_INVALID','error':str(exc),
                          'scientific_release':'NOT_AUTHORIZED'}))
        sys.exit(1)
    print(json.dumps(result,indent=2))
