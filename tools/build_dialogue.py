"""Compile curated dialogue into native Emuera code; no runtime dependency."""
import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'content/dialogue_sample.json'
OUTPUT = ROOT / 'ERB/DIALOGUE_STORIES.ERB'


def compile_stories():
    data = json.loads(SOURCE.read_text(encoding='utf-8-sig'))
    extra = json.loads((ROOT / 'content/character_stories.json').read_text(encoding='utf-8-sig'))
    data['packs'].extend(extra['packs'])
    lines = ['; 由 tools/build_dialogue.py 从 content/dialogue_sample.json 生成。',
             '; 编辑源文本后重新生成；正式游戏直接执行本ERB。',
             '@DIALOGUE_STORY(DL_P, DL_PACK, DL_EVENT)',
             '#DIM DYNAMIC DL_P', '#DIM DYNAMIC DL_PACK', '#DIM DYNAMIC DL_EVENT',
             '#DIM DYNAMIC DL_FIRST', '#DIM DYNAMIC DL_SECOND',
             '#DIM DYNAMIC DL_TRUST', '#DIM DYNAMIC DL_AGREE',
             '#DIM DYNAMIC DL_DECISIVE', '#DIM DYNAMIC DL_SUCCESS', 'SELECTCASE DL_PACK']
    seen = set()

    def prose(items, indent):
        for item in items:
            if isinstance(item, dict):
                assert set(item) == {'0', '1', '2', '3'}, 'All attitude states need authored prose'
                lines.append(indent + 'SELECTCASE DIALOGUE_ATTITUDE(DL_P)')
                for phase in range(4):
                    assert isinstance(item[str(phase)], list) and item[str(phase)]
                    lines.append(indent + f'CASE {phase}')
                    prose(item[str(phase)], indent + '\t')
                lines.append(indent + 'ENDSELECT')
                continue
            remaining = re.sub(r'\{(?:name|master|self|address)\}', '', item)
            assert '\n' not in item and not any(c in remaining for c in '%{}'), item
            runtime_text = item.replace('{name}', '__NPC_NAME__').replace('{master}', '__MASTER_NAME__').replace('{self}', '__SELF_CALL__').replace('{address}', '__MASTER_ADDRESS__')
            lines.append(indent + 'CALL DIALOGUE_PROSE(DL_P, ' + json.dumps(runtime_text, ensure_ascii=False) + ')')

    for pack in data['packs']:
        assert len(pack['events']) == 4
        lines += [f"CASE {pack['id']}", '\tSELECTCASE DL_EVENT']
        for no, event in enumerate(pack['events'], 1):
            assert (pack['id'], no) not in seen
            seen.add((pack['id'], no))
            lines.append(f'\tCASE {no}')
            lines.append('\t\tCALL DIALOGUE_SCENE_HEADER(DL_P, ' + json.dumps(event['title'], ensure_ascii=False) + ')')
            prose(event['body'], '\t\t')
            for rnd, field in [(1, 'first'), (2, 'second')]:
                if rnd == 2:
                    prose(event['bridge'], '\t\t')
                choices = event[field]
                assert len(choices) == 3
                assert sum(c['trust'] + c['agree'] >= 12 for c in choices) >= 1
                for i, c in enumerate(choices, 1):
                    lines.append(f'\t\tCALL DIALOGUE_STORY_OPTION(DL_P, {i}, ' + json.dumps(c['text'], ensure_ascii=False) + ')')
                lines += ['\t\tCALL DIALOGUE_OPTION(0, "结束这次交谈")', '\t\tCALL DIALOGUE_CHOOSE(3)',
                          '\t\t' + ('DL_FIRST' if rnd == 1 else 'DL_SECOND') + ' = RESULT',
                          '\t\tSIF RESULT == 0', '\t\t\tRETURN 0, DL_FIRST, 0, 0, 0',
                          '\t\tSELECTCASE RESULT']
                for i, c in enumerate(choices, 1):
                    lines.append(f'\t\tCASE {i}')
                    prose(c['reply'], '\t\t\t')
                    lines += [f"\t\t\tDL_TRUST += {c['trust']}", f"\t\t\tDL_AGREE += {c['agree']}"]
                    if rnd == 2:
                        lines.append(f"\t\t\tDL_DECISIVE = {int(c['trust'] + c['agree'] >= 12)}")
                lines.append('\t\tENDSELECT')
            lines += ['\t\tDL_SUCCESS = DL_TRUST + DL_AGREE >= 20',
                      '\t\tSIF DL_EVENT == 3 && DL_DECISIVE == 0', '\t\t\tDL_SUCCESS = 0',
                      '\t\tSIF DL_EVENT == 4 && DL_TRUST + DL_AGREE < 24', '\t\t\tDL_SUCCESS = 0',
                      '\t\tIF DL_SUCCESS']
            prose(event['ending'], '\t\t\t')
            lines += ['\t\tELSE', '\t\t\tCALL DIALOGUE_PROSE(DL_P, "………看来对方还没有被说服。这件事，还是下次再谈吧。")',
                      '\t\tENDIF', '\t\tRETURN 1, DL_FIRST, DL_SECOND, DL_TRUST, DL_AGREE, DL_SUCCESS']
        lines.append('\tENDSELECT')
    lines += ['ENDSELECT', 'RETURN 0, 0, 0, 0, 0', '',
              '@DIALOGUE_EVENT_TITLE(DL_PACK, DL_EVENT)', '#FUNCTIONS',
              '#DIM DYNAMIC DL_PACK', '#DIM DYNAMIC DL_EVENT', 'SELECTCASE DL_PACK']
    for pack in data['packs']:
        lines += [f"CASE {pack['id']}", '\tSELECTCASE DL_EVENT']
        for i, event in enumerate(pack['events'], 1):
            lines += [f'\tCASE {i}', '\t\tRETURNF ' + json.dumps(event['title'], ensure_ascii=False)]
        lines.append('\tENDSELECT')
    lines += ['ENDSELECT', 'RETURNF "日常交谈"', '',
              '@DIALOGUE_CHOICE_TEXT(DL_PACK, DL_EVENT, DL_ROUND, DL_PICK)', '#FUNCTIONS',
              '#DIM DYNAMIC DL_PACK', '#DIM DYNAMIC DL_EVENT', '#DIM DYNAMIC DL_ROUND',
              '#DIM DYNAMIC DL_PICK', 'SELECTCASE DL_PACK * 1000 + DL_EVENT * 10 + DL_ROUND']
    for pack in data['packs']:
        for i, event in enumerate(pack['events'], 1):
            for rnd, field in [(1, 'first'), (2, 'second')]:
                lines += [f"CASE {pack['id'] * 1000 + i * 10 + rnd}", '\tSELECTCASE DL_PICK']
                for pick, c in enumerate(event[field], 1):
                    lines += [f'\tCASE {pick}', '\t\tRETURNF ' + json.dumps(c['text'], ensure_ascii=False)]
                lines.append('\tENDSELECT')
    lines += ['ENDSELECT', 'RETURNF "暂时结束了交谈"', '']
    return '\r\n'.join(lines).encode('utf-8-sig'), data


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    result, data = compile_stories()
    if args.check:
        assert OUTPUT.read_bytes() == result, 'Dialogue ERB is out of date'
    else:
        OUTPUT.write_bytes(result)
    events = sum(len(p['events']) for p in data['packs'])
    print(f'PASS: {events} scenes, {events * 2} decision points, {events * 6} authored responses')
