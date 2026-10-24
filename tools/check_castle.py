"""Build isolated native-Emuera regression fixtures without changing user saves.

Usage: python tools/check_castle.py --prepare ABSOLUTE_OUTPUT_DIRECTORY
Run the copied Emuera1824cn.exe, then inspect emuera.log for assertions.
"""
import argparse
from pathlib import Path
import re
import shutil
from build_dialogue import compile_stories
from build_character_voices import compile_voices
from build_character_events import compile_events
from audit_character_coverage import inventory
from check_legacy_policy import check_policy
from build_economy import compile_rules
from build_interactions import compile_interactions

ROOT = Path(__file__).resolve().parents[1]


def check_sources():
    check_policy()
    interaction_code, _ = compile_interactions()
    assert (ROOT / 'ERB/INTERACTION_TEXT.ERB').read_bytes() == interaction_code
    interaction_functions = []
    for filename in ['INTERACTION.ERB', 'INTERACTION_TEXT.ERB']:
        interaction_functions += re.findall(r'^@(IX_\w+)', (ROOT / 'ERB' / filename).read_text(encoding='utf-8-sig'), re.M)
    assert len(interaction_functions) == len(set(interaction_functions)), 'duplicate interaction function'
    assert (ROOT / 'ERB/ECONOMY_RULES.ERB').read_bytes() == compile_rules()
    economy_functions = []
    for filename in ['ECONOMY.ERB', 'ECONOMY_RULES.ERB']:
        economy_functions += re.findall(r'^@(EC_\w+)', (ROOT / 'ERB' / filename).read_text(encoding='utf-8-sig'), re.M)
    assert len(economy_functions) == len(set(economy_functions)), 'duplicate economy function'
    tax = (ROOT / 'ERB/TAX.ERB').read_text(encoding='utf-8-sig')
    tax_entry = re.search(r'^@TAX_GET\s*\n(.*?)(?=^@)', tax, re.M | re.S).group(1)
    assert 'CALL EC_SETTLE' in tax_entry and 'MONEY +=' not in tax_entry, 'Active tax entry must settle only once'
    body = (ROOT / 'ERB/CASTLE.ERB').read_text(encoding='utf-8-sig')
    names = re.findall(r'^@(CASTLE_\w+)', body, re.M)
    assert len(names) == len(set(names)), 'duplicate castle function'
    headers = (ROOT / 'ERB/CASTLE.ERH').read_text(encoding='utf-8-sig')
    assert 'SAVEDATA CHARADATA CASTLE_PERSON' in headers
    assert not re.search(r'^#DIM (?:DYNAMIC )?[A-Z]\b', body, re.M)
    for filename in ['SHOP.ERB', 'SHOP_FUNCTION.ERB', 'TRAIN_MAIN.ERB', 'CHARA_INFO_SHOW.ERB']:
        data = (ROOT / 'ERB' / filename).read_bytes()
        assert data.startswith(b'\xef\xbb\xbf'), filename + ': missing UTF-8 BOM'
        assert 'CASTLE_' in data.decode('utf-8-sig'), filename + ': missing integration'
    # Validate block pairing independently of indentation and labels.
    dialogue_files = ['DIALOGUE_CORE.ERB', 'DIALOGUE_DAILY.ERB', 'DIALOGUE_STORIES.ERB', 'DIALOGUE_UI.ERB', 'DIALOGUE_ATTITUDE.ERB', 'DIALOGUE_VOICES.ERB', 'CHARACTER_EVENTS.ERB', 'CHARACTER_EVENTS_TEXT.ERB', 'CASTLE_POLICY.ERB', 'ECONOMY.ERB', 'ECONOMY_RULES.ERB', 'INTERACTION.ERB', 'INTERACTION_TEXT.ERB', 'CASTLE_MOVEMENT.ERB']
    voice_code, voice_data = compile_voices()
    assert (ROOT/'ERB/DIALOGUE_VOICES.ERB').read_bytes() == voice_code
    event_code, _ = compile_events()
    assert (ROOT/'ERB/CHARACTER_EVENTS_TEXT.ERB').read_bytes() == event_code
    audit_data, _ = inventory()
    assert (ROOT/'docs/character_coverage.json').read_bytes() == audit_data
    for filename in ['CHARACTER_EVENTS.ERB', 'CHARACTER_EVENTS_TEXT.ERB']:
        active = '\n'.join(l.split(';',1)[0] for l in (ROOT/'ERB'/filename).read_text(encoding='utf-8-sig').splitlines())
        assert not re.search(r'\bRAND\b', active), 'Event display must not consume combat randomness'
    for filename,actor in [('DUNGEON.ERB','ARG:0'),('侵略/AGENT/AGENT.ERB','ARG:0'),('LABO_DUNGEON_MAP.ERB','A')]:
        code=(ROOT/'ERB'/filename).read_text(encoding='utf-8-sig')
        jumps=[line.strip() for line in code.splitlines() if line.strip().startswith('JUMP ENDING_2')]
        assert jumps == [f'JUMP ENDING_2({actor})'], 'Castle fall must receive the actual expedition leader'
    generated, story_data = compile_stories()
    assert (ROOT/'ERB/DIALOGUE_STORIES.ERB').read_bytes() == generated
    # Captive prose must be authored for each attitude, including the response to choices.
    for pack in story_data['packs']:
        for event in pack['events']:
            for field in ['body', 'bridge', 'ending']:
                assert all(isinstance(node, dict) and set(node) == {'0','1','2','3'} for node in event[field])
            for field in ['first', 'second']:
                for choice in event[field]:
                    for node in choice['reply']:
                        assert isinstance(node, dict) and set(node) == {'0','1','2','3'}
                        if pack['id'] == 10:
                            assert node['0'] != node['1'] and node['1'] != node['2'], 'White Clover replies must evolve with attitude'
                            for phase in ['0', '1', '2']:
                                assert not any(term in ''.join(node[phase]) for term in ['魔王大人','主人'])
    all_functions = []
    for filename in dialogue_files:
        data = (ROOT/'ERB'/filename).read_bytes()
        assert data.startswith(b'\xef\xbb\xbf'), filename
        all_functions += re.findall(r'^@((?:DIALOGUE|CHARACTER)_\w+)', data.decode('utf-8-sig'), re.M)
    assert len(all_functions) == len(set(all_functions)), 'duplicate dialogue function'
    for filename in ['CASTLE.ERB', 'SHOP.ERB', 'SHOP_FUNCTION.ERB', 'TRAIN_MAIN.ERB', 'EVENT_K.ERB', 'ENDING.ERB'] + dialogue_files:
        stack = []
        pending_single = False
        for no, raw in enumerate((ROOT/'ERB'/filename).read_text(encoding='utf-8-sig').splitlines(), 1):
            line = raw.strip()
            if not line or line.startswith((';', '#', '[', '$')):
                continue
            op = line.split()[0].upper()
            if op.startswith('@'):
                assert not stack, (filename, no, stack)
            if op in ('IF', 'FOR', 'REPEAT', 'WHILE', 'SELECTCASE', 'DO'):
                stack.append((op, no))
            elif op in ('ENDIF', 'NEXT', 'REND', 'WEND', 'ENDSELECT', 'LOOP'):
                expected = {'ENDIF':'IF','NEXT':'FOR','REND':'REPEAT','WEND':'WHILE','ENDSELECT':'SELECTCASE','LOOP':'DO'}[op]
                assert stack and stack[-1][0] == expected, (filename, no, line, stack)
                stack.pop()
        assert not stack, (filename, stack)
    print('PASS: saved character data, integrations, identifiers, encoding and block structure')


def prepare(destination, load_save=None, scripted=False, interactive=False, expected_guard=2, saved_scenario="default", dialogue=False, identity=False):
    destination = destination.resolve()
    assert not destination.exists(), 'Use a new directory for each fixture'
    assert destination != ROOT and ROOT not in destination.parents, 'Fixture must be outside game directory'
    destination.mkdir(parents=True)
    for directory in ['ERB', 'CSV', 'resources']:
        shutil.copytree(ROOT / directory, destination / directory)
    for filename in ['Emuera1824cn.exe', 'emuera.config']:
        shutil.copy2(ROOT / filename, destination / filename)
    config = destination/'emuera.config'
    config_text = config.read_text(encoding='utf-8-sig').replace('オートセーブを行なう:YES','オートセーブを行なう:NO')
    if dialogue:
        config_text = config_text.replace('履歴ログの行数:5000', '履歴ログの行数:30000')
    config.write_text(config_text,encoding='utf-8-sig')
    (destination / 'sav').mkdir()
    harness = (ROOT / 'tests/castle_engine.ERB.txt').read_text(encoding='utf-8-sig')
    if scripted or dialogue or identity:
        assert not load_save, 'Interaction fixture must start with synthetic data'
        assert sum([scripted,dialogue,identity])==1, 'Choose one suite'
        entry = 'IP_RUN' if identity else ('DT_RUN' if dialogue else 'CT_INTERACTIONS')
        testfile = 'identity_engine.ERB.txt' if identity else ('dialogue_engine.ERB.txt' if dialogue else 'castle_interactions.ERB.txt')
        harness = harness.replace('LOCALS = castle regression only',f'CALL {entry}\nLOCALS = castle regression only')
        harness += '\n' + (ROOT/'tests'/testfile).read_text(encoding='utf-8-sig')
        if dialogue:
            harness += '\n' + (ROOT/'tests/character_voice_engine.ERB.txt').read_text(encoding='utf-8-sig')
            harness += '\n' + (ROOT/'tests/character_events_engine.ERB.txt').read_text(encoding='utf-8-sig')
            _, voices = compile_voices()
            harness += '\n@DT_VOICE_ID(DT_I)\n#FUNCTION\n#DIM DYNAMIC DT_I\nSELECTCASE DT_I\n'
            for i, profile in enumerate(voices['profiles']):
                harness += f'CASE {i}\n\tRETURNF {profile["id"]}\n'
            harness += 'ENDSELECT\nRETURNF -1\n'
        # Choice helpers come from the authored scripts, while state/resource assertions are independent.
        _, stories = compile_stories()
        harness += '\n@DT_CHOICE(DT_PACK, DT_EVENT, DT_ROUND, DT_GOOD = 1)\n#FUNCTION\n#DIM DYNAMIC DT_PACK\n#DIM DYNAMIC DT_EVENT\n#DIM DYNAMIC DT_ROUND\n#DIM DYNAMIC DT_GOOD\nSELECTCASE DT_PACK * 1000 + DT_EVENT * 10 + DT_ROUND\n'
        for pack in stories['packs']:
            for event_no, event in enumerate(pack['events'], 1):
                for rnd, field in [(1, 'first'), (2, 'second')]:
                    ranks = [c['trust'] + c['agree'] for c in event[field]]
                    good, bad = ranks.index(max(ranks)) + 1, ranks.index(min(ranks)) + 1
                    harness += f"CASE {pack['id'] * 1000 + event_no * 10 + rnd}\n\tRETURNF DT_GOOD ? {good} # {bad}\n"
        harness += 'ENDSELECT\nRETURNF 0\n'
        (destination/'ERB/CASTLE_TEST.ERH').write_text('#DIM CT_QUEUE, 32\n#DIM CT_POS\n#DIM CT_SIZE\n',encoding='utf-8-sig')
        for name in ['CASTLE.ERB', 'ECONOMY.ERB', 'DIALOGUE_CORE.ERB', 'DIALOGUE_DAILY.ERB', 'DIALOGUE_UI.ERB', 'INTERACTION.ERB']:
            module = destination/'ERB'/name
            code = module.read_text(encoding='utf-8-sig')
            code = re.sub(r'(?m)^([ \t]*)INPUT[ \t]*$',r'\1CALL CT_INPUT',code)
            code = re.sub(r'\bPRINTW\b','PRINTL',code)
            code = re.sub(r'\bPRINTFORMW\b','PRINTFORML',code)
            module.write_text(code,encoding='utf-8-sig')
        if identity:
            for name in ['CHARA_INFO.ERB','CHARA_INFO_FUNC.ERB','CHARA_INFO_SHOW.ERB','SHOP_2.ERB','EXECUTION.ERB','SELL_CHARA.ERB','EVENT_CHARA_LEAVE.ERB','侵略/AGENT/AGENT_EVENT.ERB','侵略/CAMPAIGN/CAMPAIGN_EVENT.ERB']:
                module=destination/'ERB'/name
                code=module.read_text(encoding='utf-8-sig')
                code=re.sub(r'(?m)^([ \t]*)INPUT[ \t]*$',r'\1CALL CT_INPUT',code)
                code=re.sub(r'\bPRINTW\b','PRINTL',code)
                code=re.sub(r'\bPRINTFORMW\b','PRINTFORML',code)
                module.write_text(code,encoding='utf-8-sig')
        if dialogue:
            # Execute the real safe ending body, replacing only waits and process exit.
            module=destination/'ERB/ENDING.ERB'
            code=module.read_text(encoding='utf-8-sig')
            match=re.search(r'^@ENDING_2\([^\n]*\n.*?(?=^@ENDING_3)',code,re.M|re.S)
            assert match
            block=match.group(0).replace('PRINTFORMW','PRINTFORML')
            block=re.sub(r'(?m)^INPUT\s*$','CALL CT_INPUT',block)
            block=re.sub(r'(?m)^QUIT\s*$','RETURN 0',block)
            module.write_text(code[:match.start()]+block+code[match.end():],encoding='utf-8-sig')
    if load_save:
        shutil.copy2(load_save, destination / 'sav/save98.sav')
        assertions = harness[harness.index('@CT_ASSERT'):]
        harness = '''@SYSTEM_TITLE
LOADDATA 98

@CT_AFTER_LOAD
#DIM DYNAMIC CT_PEOPLE
#DIM DYNAMIC CT_MONEY
#DIM DYNAMIC CT_TROOPS
#DIM DYNAMIC CT_OLD_VERSION
#DIM DYNAMIC CT_DAY
CT_PEOPLE = CHARANUM
CT_MONEY = MONEY
CT_TROOPS = CASTLE_TROOP_TOTAL()
CT_OLD_VERSION = CASTLE_STATE:0
CT_DAY = DAY
CALL CHARA_NAME_INIT
CALL CASTLE_SYNC
CALL CT_ASSERT(CHARANUM == CT_PEOPLE, "load preserves people")
CALL CT_ASSERT(MONEY == CT_MONEY, "load preserves money")
CALL CT_ASSERT(CASTLE_TROOP_TOTAL() == CT_TROOPS, "load preserves troops")
CALL CT_ASSERT(DAY == CT_DAY, "load preserves time")
CALL CT_ASSERT(CASTLE_STATE:0 == 3, "load initializes module")
IF CT_OLD_VERSION >= 2
    CALL CT_ASSERT(CASTLE_PERSON:2:CP_HOME == CL_CHAMBER, "save restores residence")
    CALL CT_ASSERT(CASTLE_PERSON:2:CP_WORK == CL_BARRACKS, "save restores appointment")
    CALL CT_ASSERT(CASTLE_PERSON:2:CP_ORIGIN == 2, "save restores training allegiance source")
    CALL CT_ASSERT(CASTLE_GUARD:170 == 2, "save restores troop allocation")
    CALL CT_ASSERT(CASTLE_LEVEL:CL_BARRACKS == 3, "save restores facility level")
    CALL CT_ASSERT(CASTLE_STATE:2 == CL_BARRACKS, "save restores player location")
ENDIF
PRINTL CASTLE LOAD ASSERTIONS PASSED
CALL CASTLE_DRAW
OUTPUTLOG
QUIT

''' + assertions
        if saved_scenario == 'dialogue':
            harness = harness.replace('CP_HOME == CL_CHAMBER', 'CP_HOME == CL_QUARTERS').replace('CP_WORK == CL_BARRACKS', 'CP_WORK == 0').replace('CP_ORIGIN == 2', 'CP_ORIGIN == 3').replace('CASTLE_STATE:2 == CL_BARRACKS', 'CASTLE_STATE:2 == CL_DUNGEON')
            harness = harness.replace('PRINTL CASTLE LOAD ASSERTIONS PASSED', 'CALL CT_ASSERT(CASTLE_PERSON:2:CP_PERSUADE == 100, "save restores dialogue progress")\nPRINTL CASTLE LOAD ASSERTIONS PASSED')
        elif saved_scenario == 'guest':
            harness = harness.replace('CP_HOME == CL_CHAMBER', 'CP_HOME == CL_DUNGEON').replace('CP_WORK == CL_BARRACKS', 'CP_WORK == 0').replace('CP_ORIGIN == 2', 'CP_ORIGIN == 0').replace('CASTLE_STATE:2 == CL_BARRACKS', 'CASTLE_STATE:2 == CL_CHAMBER')
            harness = harness.replace('PRINTL CASTLE LOAD ASSERTIONS PASSED', 'CALL CT_ASSERT(CASTLE_STATE:6 == CASTLE_PERSON:2:CP_UID && CASTLE_WHERE(2) == CL_CHAMBER, "save restores temporary guest without residence change")\nPRINTL CASTLE LOAD ASSERTIONS PASSED')
        elif saved_scenario in ('story', 'story_pending'):
            pending = saved_scenario == 'story_pending'
            harness = harness.replace('CP_HOME == CL_CHAMBER', 'CP_HOME == ' + ('CL_DUNGEON' if pending else 'CL_QUARTERS')).replace('CP_WORK == CL_BARRACKS', 'CP_WORK == 0').replace('CP_ORIGIN == 2', 'CP_ORIGIN == ' + ('0' if pending else '3')).replace('CASTLE_STATE:2 == CL_BARRACKS', 'CASTLE_STATE:2 == CL_DUNGEON')
            extra = f'CALL CT_ASSERT(DIALOGUE_PERSON:2:DP_CHAPTER == {3 if pending else 4}, "save restores story chapter")\n'
            extra += f'CALL CT_ASSERT(DIALOGUE_PERSON:2:DP_PROMISE == {1 if pending else 2}, "save restores promise state")\n'
            extra += 'CALL CT_ASSERT(DIALOGUE_PERSON:2:DP_SPECIAL == 170 && DIALOGUE_PACK(2) == 10, "save restores unique character script")\n'
            extra += 'CALL CT_ASSERT(DIALOGUE_PERSON:2:DP_CHOICE1 > 0 && DIALOGUE_PERSON:2:DP_CHOICE2 > 0, "save restores chosen responses")\n'
            extra += 'CALL CT_ASSERT(DIALOGUE_PERSON:2:DP_VERSION == 2 && DIALOGUE_PERSON:2:DP_MET == 1, "save preserves or migrates first encounter state")\n'
            extra += 'CALL CT_ASSERT(DIALOGUE_ADDRESS(2) == "你", "loaded White Clover keeps original address")\n'
            harness = harness.replace('PRINTL CASTLE LOAD ASSERTIONS PASSED', extra + 'PRINTL CASTLE LOAD ASSERTIONS PASSED')
        elif saved_scenario == 'economy_legacy':
            extra = 'CALL CT_ASSERT(EC_STATE:EC_VERSION == 1 && EC_STOCK:1 == 120 && EC_STOCK:2 == 60 && EC_STOCK:3 == 30, "original save receives initial economy supplies exactly once")\n'
            extra += 'EC_STOCK:3 = 19\nCALL CASTLE_SYNC\nCALL CT_ASSERT(EC_STOCK:3 == 19 && MONEY == CT_MONEY, "old save refresh does not duplicate supplies or change cash")\n'
            harness = harness.replace('PRINTL CASTLE LOAD ASSERTIONS PASSED', extra + 'PRINTL CASTLE LOAD ASSERTIONS PASSED')
        harness = harness.replace('CASTLE_GUARD:170 == 2' , 'CASTLE_GUARD:170 == ' + str(expected_guard))
        system = destination/'ERB/SYSTEM.ERB'
        source = system.read_text(encoding='utf-8-sig')
        assert source.count('@EVENTLOAD') == 1
        system.write_text(source.replace('@EVENTLOAD','@EVENTLOAD\nCALL CT_AFTER_LOAD',1),encoding='utf-8-sig')
        if interactive:
            harness = '@SYSTEM_TITLE\nLOADDATA 98\n'
            system.write_text(source, encoding='utf-8-sig')
    (destination / 'ERB/TITLE.ERB').write_text(harness, encoding='utf-8-sig')
    print(destination / 'Emuera1824cn.exe')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--prepare', type=Path)
    parser.add_argument('--load-save', type=Path)
    parser.add_argument('--scripted-interactions', action='store_true')
    parser.add_argument('--interactive', action='store_true', help='Open copied save through original EVENTLOAD and SHOP')
    parser.add_argument('--dialogue', action='store_true', help='Run dialogue stories, branching, migration and resource regression suite')
    parser.add_argument('--identity', action='store_true', help='Run shared identity, legacy entry and lifecycle regression suite')
    parser.add_argument('--saved-scenario', choices=['default', 'dialogue', 'guest', 'story', 'story_pending', 'economy_legacy'], default='default')
    parser.add_argument('--expected-guard', type=int, default=2, help='Expected troop allocation for a known synthetic save; scripted fixture uses 4')
    args = parser.parse_args()
    check_sources()
    if args.prepare:
        prepare(args.prepare, args.load_save, args.scripted_interactions, args.interactive, args.expected_guard, args.saved_scenario, args.dialogue, args.identity)
