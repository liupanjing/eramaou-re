"""Generate an honest static coverage inventory without quoting adult prose."""
import argparse
import json
import re
from pathlib import Path

from build_character_events import compile_events
from build_character_voices import compile_voices
from build_dialogue import compile_stories

ROOT=Path(__file__).resolve().parents[1]
OUTPUT=ROOT/'docs/character_coverage.json'


def active_text(text):
    result=[]
    skipped=False
    for line in text.splitlines():
        stripped=line.strip()
        if stripped=='[SKIPSTART]': skipped=True; continue
        if stripped=='[SKIPEND]': skipped=False; continue
        if not skipped and stripped and not stripped.startswith(';'):
            result.append(line)
    return '\n'.join(result)


def inventory():
    _,voices=compile_voices()
    _,events=compile_events()
    _,stories=compile_stories()
    legacy=[]
    for path in sorted((ROOT/'ERB').glob('EVENT_K*.ERB')):
        if path.name=='EVENT_K.ERB': continue
        text=path.read_text(encoding='utf-8-sig')
        headers=list(re.finditer(r'^@([^\s(,]+)',text,re.M))
        sections=[]
        for i,match in enumerate(headers):
            block=active_text(text[match.end():headers[i+1].start() if i+1<len(headers) else None])
            prints=re.findall(r'(?m)^\s*PRINT(?:FORM[WL]?|[WL]|S)?\s+([^\n]+)',block)
            prints=[s for s in prints if s.strip() not in ['""','@""']]
            command_ids=sorted({int(x) for x in re.findall(r'\bSELECTCOM\s*==\s*(\d+)',block)})
            sections.append(dict(function=match.group(1),line=text.count('\n',0,match.start())+1,
                                 static_prints=len(prints),status='has_text' if prints else 'declaration_or_delegation_only',
                                 command_conditions=command_ids))
        legacy.append(dict(file=path.relative_to(ROOT).as_posix(),sections=sections,
                           caveat='静态PRINT存在不等于该函数所有条件分支都有口上；未逐条改写成人文本。'))
    # Verify each advertised hook inside the actual function, not just metadata.
    contracts={
      1:[('EVENT_K.ERB','ATTACK_KOUJO','CE_ATTACK'),('EVENT_K.ERB','ATTACK_KOUJO_B','CE_ATTACK')],
      2:[('EVENT_K.ERB','VICTORY_KOUJO','CE_VICTORY')],
      3:[('EVENT_K.ERB','ENTERENEMY_KOUJO','CE_ARRIVAL')],
      4:[('CASTLE.ERB','CASTLE_PERSON_MENU','CE_JOIN'),('CASTLE.ERB','CASTLE_COMMAND','CE_JOIN')],
      5:[('CASTLE.ERB','CASTLE_ASSIGN','CE_HOME')],
      6:[('CASTLE.ERB','CASTLE_ASSIGN','CE_JOB')],
      7:[('CASTLE.ERB','CASTLE_ASSIGN','CE_JOB_CLEAR')],
      8:[('CASTLE.ERB','CASTLE_COMMAND','CHARACTER_LOCAL_REST')],
      9:[('ENDING.ERB','ENDING_1','CE_WORLD_END')],
      10:[('ENDING.ERB','ENDING_3','CE_REALM_END'),('ENDING.ERB','ENDING_4','CE_REALM_END'),('ENDING.ERB','ENDING_5','CE_REALM_END')],
      11:[('ENDING.ERB','ENDING_2','CE_CASTLE_FALL')],
      12:[('ENDING.ERB','ENDING_N','CE_NORMAL_END')],
    }
    hooks=[]
    for event in events['events']:
        checked=[]
        for filename,function,token in contracts[event['id']]:
            code=(ROOT/'ERB'/filename).read_text(encoding='utf-8-sig')
            match=re.search(r'^@'+re.escape(function)+r'(?=[(,\s]|$)[^\n]*\n(.*?)(?=^@|\Z)',code,re.M|re.S)
            assert match, (filename,function)
            block=active_text(match.group(1))
            assert any('CALL CHARACTER_' in line and re.search(r'\b'+token+r'\b',line) for line in block.splitlines()), (filename,function,token)
            checked.append(f'ERB/{filename}:{function}')
        hooks.append(dict(id=event['id'],name=event['name'],key=event['key'],hook=event['hook'],
                          authored_profiles=len(events['profiles']),defined_attitudes=event['phases'],
                          checked_functions=checked,status='native_hook_connected'))
    report=dict(schema_version=1,
      scope='新增非露骨城内、战斗与结局反应；不宣称全部成人口上已补齐。',
      profiles=[dict(id=p['id'],name=p['name'],kind=p['kind']) for p in voices['profiles']],
      new_coverage=dict(voice_profiles=len(voices['profiles']),first_encounter_profiles=len(voices['profiles']),
                        story_packs=len(stories['packs']),story_scenes=sum(len(p['events']) for p in stories['packs']),
                        event_hooks=hooks,
                        event_branch_slots=sum(len(e['phases']) for e in events['events'])*len(events['profiles']),
                        note='分支槽数包含有意复用的台词，不是互不重复的新增台词数量；实际触发仍受身份、年龄、在场及口上开关限制。'),
      retained_legacy=legacy,
      explicitly_not_completed=[
        dict(category='露骨性行为与强迫性调教口上',status='not_newly_authored'),
        dict(category='含露骨内容的个人成人结局',status='retained_legacy_not_rewritten'),
        dict(category='未实装的狂王本尊主线结局',status='not_invented_by_voice_extension')],
      protections=['年幼角色仅新增非性内容。','加入、迁居与任职的成功反应不会在取消或失败时触发。',
                   '事件显示不改写金钱、行动、人物属性、既有选择和结局标志，也不消耗RAND。'])
    return (json.dumps(report,ensure_ascii=False,indent=2)+'\n').encode('utf-8'),report


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    data,report=inventory()
    if args.check:
        assert OUTPUT.read_bytes()==data,'Coverage inventory is stale'
    else:
        OUTPUT.write_bytes(data)
    print(f'PASS: {len(report["profiles"])} profiles, {len(report["new_coverage"]["event_hooks"])} connected event types; adult-text gaps explicitly listed')
