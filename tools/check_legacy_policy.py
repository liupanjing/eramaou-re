"""Check that advertised old entry guards are present before any effects."""
import json
import re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def check_policy():
    manifest=json.loads((ROOT/'content/legacy_policy_hooks.json').read_text(encoding='utf-8-sig'))
    for entry in manifest['guards']:
        code=(ROOT/entry['file']).read_text(encoding='utf-8-sig')
        match=re.search(r'^@'+re.escape(entry['function'])+r'(?=[(,\s]|$)[^\n]*\n(.*?)(?=^@|\Z)',code,re.M|re.S)
        assert match,(entry['file'],entry['function'])
        lines=[s.strip() for s in match.group(1).splitlines() if s.strip() and not s.strip().startswith((';','#'))]
        if 'call' in entry:
            assert lines[0]==entry['call'],entry
        else:
            assert lines[:2]==['SIF '+entry['condition'],entry['return_statement']],entry
    policy=(ROOT/'ERB/CASTLE_POLICY.ERB').read_text(encoding='utf-8-sig')
    active='\n'.join(line.split(';',1)[0] for line in policy.splitlines())
    assert not re.search(r'\b(?:RAND|INPUT|WAIT|PRINTW|PRINTFORMW)\b',active)
    assert 'SIF CASTLE_ACCESS_REASON(TARGET, CA_DISPOSE)' in (ROOT/'ERB/EXECUTION.ERB').read_text(encoding='utf-8-sig')
    assert 'IF CASTLE_ACCESS_REASON(A, CA_DISPOSE)' in (ROOT/'ERB/EXECUTION.ERB').read_text(encoding='utf-8-sig')
    return manifest

if __name__=='__main__':
    data=check_policy()
    print(f'PASS: {len(data["guards"])} shared legacy entry guards and synchronization hooks')
