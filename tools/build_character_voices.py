"""Compile authored character voices and encounter text for native Emuera."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'content/character_voices.json'
OUTPUT = ROOT / 'ERB/DIALOGUE_VOICES.ERB'


def compile_voices():
    data = json.loads(SOURCE.read_text(encoding='utf-8-sig'))
    profiles = data['profiles']
    ids = [p['id'] for p in profiles]
    assert len(ids) == len(set(ids))
    assert set(range(160, 176)) <= set(ids), 'All original personality types need distinct voices'
    lines = ['; 由 tools/build_character_voices.py 生成，原有EVENT_K文件不改写。',
             '@DIALOGUE_PROFILE(DL_P)', '#FUNCTION', '#DIM DYNAMIC DL_P',
             'SIF DL_P < 0 || DL_P >= CHARANUM', '\tRETURNF 0']
    for category in ['csv', 'ex', 'talents']:
        for profile in profiles:
            if profile.get('kind') != 'unique':
                continue
            checks = [({'csv': 'NO:DL_P == ', 'ex': 'EX_TALENT:DL_P:', 'talents': 'TALENT:DL_P:'}[category] + str(n)) for n in profile.get(category, [])]
            if checks:
                lines += ['SIF ' + ' || '.join(checks), f'\tRETURNF {profile["id"]}']
    # Original personality precedence mirrors GET_KOJO_NUM: highest marker wins.
    for marker in range(175, 159, -1):
        lines += [f'SIF TALENT:DL_P:{marker}', f'\tRETURNF {marker}']
    unique_ids = ', '.join(str(p['id']) for p in profiles if p.get('kind') == 'unique')
    lines += ['IF DIALOGUE_PERSON:DL_P:DP_VERSION == 0',
              '\tSIF TALENT:DL_P:10', '\t\tRETURNF 2',
              '\tSIF TALENT:DL_P:22', '\t\tRETURNF 3',
              '\tSIF TALENT:DL_P:15 || TALENT:DL_P:16', '\t\tRETURNF 4',
              '\tSIF TALENT:DL_P:12 || TALENT:DL_P:11', '\t\tRETURNF 1',
              '\tSIF TALENT:DL_P:13', '\t\tRETURNF 5', 'ENDIF',
              'RETURNF DIALOGUE_PERSON:DL_P:DP_TEMPER', '',
              '@DIALOGUE_IS_UNIQUE(DL_P)', '#FUNCTION', '#DIM DYNAMIC DL_P',
              'SELECTCASE DIALOGUE_PROFILE(DL_P)', 'CASE ' + unique_ids,
              '\tRETURNF 1', 'ENDSELECT', 'RETURNF 0', '',
              '@DIALOGUE_SELF(DL_P)', '#FUNCTIONS', '#DIM DYNAMIC DL_P',
              'SIF STRLENS(CSTR:DL_P:60) > 0', '\tRETURNF CSTR:DL_P:60',
              'SELECTCASE DIALOGUE_PROFILE(DL_P)']
    for p in profiles:
        lines += [f'CASE {p["id"]}', '\tRETURNF ' + json.dumps(p.get('self', '我'), ensure_ascii=False)]
    lines += ['ENDSELECT', 'RETURNF SELF_CALL(DL_P)', '',
              '@DIALOGUE_CHARACTER_TEXT(DL_P, DL_KIND, DL_VARIANT = 0)', '#FUNCTIONS',
              '#DIM DYNAMIC DL_P', '#DIM DYNAMIC DL_KIND', '#DIM DYNAMIC DL_VARIANT',
              '#DIM DYNAMIC DL_PHASE', 'DL_PHASE = DIALOGUE_ATTITUDE(DL_P)',
              '; 没有旧话题记录时，招呼使用不依赖具体往事的本人口吻。',
              'SIF DL_KIND == 1 && DIALOGUE_HAS_HISTORY(DL_P) == 0 && DIALOGUE_SEEN:DL_P:10 == 0',
              '\tDL_KIND = 7',
              '; 已归顺但信任低时仍有本人的保留，不自动成为亲近或温顺口吻。',
              'IF CASTLE_PERSON:DL_P:CP_ROLE == CR_FOLLOWER && (DIALOGUE_PERSON:DL_P:DP_TRUST < 15 || DIALOGUE_PERSON:DL_P:DP_AGREE < 15)',
              '\tSIF DL_KIND == 1 || DL_KIND == 7', '\t\tDL_KIND = 9',
              '\tSIF DL_KIND == 2', '\t\tDL_KIND = 10', 'ENDIF',
              'SELECTCASE DIALOGUE_PROFILE(DL_P)']
    # Kinds: 0 first encounter, 1 revisit greeting, 2 daily, 3 positive reply,
    # 4 neutral reply, 5 negative reply, 6 formal/current address, 7 voice line.
    fields = ['intro', 'greeting', 'daily', 'positive', 'neutral', 'negative', 'address', 'voice', 'delivery', 'reserved_greeting', 'reserved_daily']
    for p in profiles:
        assert all((ROOT / e['file']).is_file() for e in p['evidence'])
        lines += [f'CASE {p["id"]}', '\tSELECTCASE DL_KIND']
        for kind, field in enumerate(fields):
            states = p[field]
            assert set(states) == {'0', '1', '2', '3'}, (p['name'], field)
            lines += [f'\tCASE {kind}', '\t\tSELECTCASE DL_PHASE']
            for phase in range(4):
                text = states[str(phase)]
                assert isinstance(text, list) and text
                lines += [f'\t\tCASE {phase}', f'\t\t\tSELECTCASE DL_VARIANT % {len(text)}']
                for i, paragraph in enumerate(text):
                    assert isinstance(paragraph, str) and paragraph
                    rest = paragraph
                    for token in ['name', 'master', 'self', 'address']:
                        rest = rest.replace('{' + token + '}', '')
                    assert not any(c in rest for c in '%{}\n'), (p['name'], field, paragraph)
                    for a, b in [('name', 'NPC_NAME'), ('master', 'MASTER_NAME'), ('self', 'SELF_CALL'), ('address', 'MASTER_ADDRESS')]:
                        paragraph = paragraph.replace('{' + a + '}', '__' + b + '__')
                    lines += [f'\t\t\tCASE {i}', '\t\t\t\tRETURNF ' + json.dumps(paragraph, ensure_ascii=False)]
                lines += ['\t\t\tENDSELECT']
            lines += ['\t\tENDSELECT']
        lines += ['\tENDSELECT']
    lines += ['ENDSELECT', 'RETURNF "………"', '']
    return '\r\n'.join(lines).encode('utf-8-sig'), data


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    generated, data = compile_voices()
    if args.check:
        assert OUTPUT.read_bytes() == generated
    else:
        OUTPUT.write_bytes(generated)
    print(f'PASS: {len(data["profiles"])} distinct voice profiles with first-encounter and four attitude states')
