"""Compile non-graphic character reactions for real game event hooks."""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'content/character_events.json'
OUTPUT = ROOT / 'ERB/CHARACTER_EVENTS_TEXT.ERB'


def compile_events():
    source = json.loads(SOURCE.read_text(encoding='utf-8-sig'))
    voices = json.loads((ROOT/'content/character_voices.json').read_text(encoding='utf-8-sig'))
    expected = {p['id'] for p in voices['profiles']}
    assert {p['id'] for p in source['profiles']} == expected
    kinds = source['events']
    assert len(kinds) == 12 and {x['id'] for x in kinds} == set(range(1, 13))
    lines = ['; 非露骨的战斗、城务和结局口上。源文件：content/character_events.json',
             '@CHARACTER_EVENT_TEXT(CE_P, CE_KIND, CE_VARIANT = 0)', '#FUNCTIONS',
             '#DIM DYNAMIC CE_P', '#DIM DYNAMIC CE_KIND', '#DIM DYNAMIC CE_VARIANT',
             '#DIM DYNAMIC CE_PHASE', 'CE_PHASE = DIALOGUE_ATTITUDE(CE_P)',
             'SELECTCASE DIALOGUE_PROFILE(CE_P)']
    for profile in source['profiles']:
        assert set(profile['events']) == {k['key'] for k in kinds}, profile['id']
        lines += [f'CASE {profile["id"]}', '\tSELECTCASE CE_KIND']
        for kind in kinds:
            states = profile['events'][kind['key']]
            assert set(states) == {str(x) for x in kind['phases']}
            lines += [f'\tCASE {kind["id"]}', '\t\tSELECTCASE CE_PHASE']
            for phase in kind['phases']:
                variants = states[str(phase)]
                assert len(variants) >= 2, (profile['id'],kind['key'],phase)
                lines += [f'\t\tCASE {phase}']
                # The first member variant retains distance; other variants need trust.
                if phase == 3 and kind['id'] > 3:
                    lines += ['\t\t\tIF CASTLE_PERSON:CE_P:CP_ROLE == CR_FOLLOWER && (DIALOGUE_PERSON:CE_P:DP_TRUST < 40 || DIALOGUE_PERSON:CE_P:DP_AGREE < 40)',
                              '\t\t\t\tCE_VARIANT = 0', '\t\t\tELSE',
                              f'\t\t\t\tCE_VARIANT = 1 + CE_VARIANT % {len(variants)-1}', '\t\t\tENDIF']
                lines += [f'\t\t\tSELECTCASE CE_VARIANT % {len(variants)}']
                for no, sentence in enumerate(variants):
                    rest = sentence
                    for token in ['name','self','master','address']:
                        rest = rest.replace('{'+token+'}', '')
                    assert sentence and not any(x in rest for x in '\n%{}'), sentence
                    for token,replacement in [('name','NPC_NAME'),('self','SELF_CALL'),('master','MASTER_NAME'),('address','MASTER_ADDRESS')]:
                        sentence=sentence.replace('{'+token+'}', '__'+replacement+'__')
                    lines += [f'\t\t\tCASE {no}', '\t\t\t\tRETURNF '+json.dumps(sentence,ensure_ascii=False)]
                lines += ['\t\t\tENDSELECT']
            lines += ['\t\tENDSELECT']
        lines += ['\tENDSELECT']
    lines += ['ENDSELECT','RETURNF ""','']
    return '\r\n'.join(lines).encode('utf-8-sig'), source


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    result, data=compile_events()
    if args.check:
        assert OUTPUT.read_bytes()==result, 'Event voices need regeneration'
    else:
        OUTPUT.write_bytes(result)
    count=sum(len(v) for p in data['profiles'] for e in p['events'].values() for v in e.values())
    print(f'PASS: {len(data["profiles"])} profiles, {len(data["events"])} event hooks, {count} non-graphic text slots (including deliberate reuse)')
