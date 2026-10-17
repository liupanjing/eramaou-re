"""Prepare real BEGIN TURNEND regression with no new random arrivals or UI waits."""
import argparse
import re
from pathlib import Path
from check_castle import ROOT, check_sources, prepare

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('destination',type=Path)
    args=parser.parse_args()
    check_sources()
    prepare(args.destination,identity=True)
    target=args.destination.resolve()
    title=target/'ERB/TITLE.ERB'
    code=title.read_text(encoding='utf-8-sig')
    code=(ROOT/'tests/identity_cycle.ERB.txt').read_text(encoding='utf-8-sig')+'\n'+code[code.index('@CT_ASSERT'):]
    title.write_bytes(code.replace('\n','\r\n').encode('utf-8-sig'))
    header=target/'ERB/CASTLE_TEST.ERH'
    with header.open('a',encoding='utf-8') as f:
        f.write('\n#DIM IC_STAGE\n#DIM IC_UID\n')
    for name in ['SYSTEM.ERB','EVENT_TURNEND.ERB','EVENT_NEXTDAY.ERB','SUMMON_MONSTER.ERB','NINSIN.ERB']:
        path=target/'ERB'/name
        code=path.read_text(encoding='utf-8-sig')
        code=re.sub(r'(?m)^([ \t]*)(?:WAIT|FORCEWAIT)[ \t]*$',r'\1RESULT = RESULT',code)
        code=re.sub(r'\bPRINTFORMW\b','PRINTFORML',code)
        code=re.sub(r'\bPRINTW\b','PRINTL',code)
        path.write_bytes(code.replace('\n','\r\n').encode('utf-8-sig'))
    path=target/'ERB/ENTER_ENEMY.ERB'
    code=path.read_text(encoding='utf-8-sig')
    code=re.sub(r'^@ENTER_ENEMY[^\n]*\n.*?(?=^@|\Z)','@ENTER_ENEMY,ARG:0\nRETURN 0\n\n',code,count=1,flags=re.M|re.S)
    path.write_bytes(code.replace('\n','\r\n').encode('utf-8-sig'))
    print('Cycle fixture uses actual day/night callbacks; only waits and external arrivals are replaced.')
