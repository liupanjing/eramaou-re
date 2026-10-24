"""Validate neutral castle interactions and compile native Emuera tables."""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'content/castle_interactions.json'
OUTPUT = ROOT / 'ERB/INTERACTION_TEXT.ERB'
TOKENS = {'name': 'NPC_NAME', 'master': 'MASTER_NAME',
          'self': 'SELF_CALL', 'address': 'MASTER_ADDRESS'}


def integer(value, lo, hi):
    assert type(value) is int and lo <= value <= hi, (value, lo, hi)
    return value


def prose(value):
    assert isinstance(value, list) and 1 <= len(value) <= 12
    for line in value:
        assert isinstance(line, str) and line.strip() and len(line) <= 800
        rest = line
        for token in TOKENS:
            rest = rest.replace('{' + token + '}', '')
        assert not any(c in rest for c in '\n\r\t%{}"\\'), 'Invalid prose token or control character'
        assert '__' not in line and not any(ord(c) < 32 for c in line)
    return value


def flatten(text):
    assert set(text) == {'opening', 'repeat', 'ending', 'rounds'}
    fields = {k: prose(text[k]) for k in ['opening', 'repeat', 'ending']}
    assert len(text['rounds']) == 2, 'The first slice supports exactly two rounds'
    for rnd, node in enumerate(text['rounds'], 1):
        assert set(node) == {'prompt', 'choices'}
        fields[f'r{rnd}'] = prose(node['prompt'])
        assert 2 <= len(node['choices']) <= 3
        for pick, choice in enumerate(node['choices'], 1):
            assert set(choice) == {'label', 'reply', 'trust', 'affection'}
            fields[f'r{rnd}c{pick}_label'] = prose([choice['label']])
            fields[f'r{rnd}c{pick}_reply'] = prose(choice['reply'])
            integer(choice['trust'], -10, 10)
            integer(choice['affection'], -100, 100)
    return fields


def field_id(key):
    if key in ('opening', 'repeat', 'ending'):
        return {'opening': 1, 'repeat': 2, 'ending': 3}[key]
    if len(key) == 2:
        return int(key[1]) * 100
    rnd, pick = int(key[1]), int(key[3])
    return rnd * 100 + pick * 10 + (1 if key.endswith('_label') else 2)


def literal(value):
    for token, target in TOKENS.items():
        value = value.replace('{' + token + '}', '__' + target + '__')
    return json.dumps(value, ensure_ascii=False)


def compile_interactions(data=None):
    if data is None:
        data = json.loads(SOURCE.read_text(encoding='utf-8-sig'))
    assert set(data) == {'schema_version', 'events'} and data['schema_version'] == 1
    events = data['events']
    assert 1 <= len(events) <= 15
    assert len({e['id'] for e in events}) == len(events)
    assert len({e['key'] for e in events}) == len(events)
    profiles = {p['id'] for p in json.loads((ROOT / 'content/character_voices.json').read_text(encoding='utf-8-sig'))['profiles']}
    compiled = {}
    required = {'id', 'key', 'title', 'status', 'locations', 'profiles', 'temperaments',
                'origins', 'min_trust', 'requires_event', 'requires_choice', 'repeatable',
                'cost', 'text', 'variants', 'author_notes'}
    for event in events:
        assert set(event) == required
        integer(event['id'], 1, 15)
        assert isinstance(event['key'], str) and event['key'].isascii() and event['key'].isidentifier()
        prose([event['title']])
        assert event['status'] in ('draft', 'ready')
        assert type(event['repeatable']) is bool
        integer(event['min_trust'], 0, 100)
        integer(event['requires_event'], 0, 15)
        integer(event['requires_choice'], 0, 33)
        assert event['requires_event'] != event['id']
        assert event['requires_event'] or event['requires_choice'] == 0
        for key, allowed in [('locations', set(range(1, 13))), ('profiles', profiles),
                             ('temperaments', set(range(7))), ('origins', set(range(1, 7)))]:
            value = event[key]
            assert isinstance(value, list) and all(type(x) is int and x in allowed for x in value)
            assert len(value) == len(set(value))
        assert event['locations']
        assert set(event['cost']) == {'actions', 'money'}
        integer(event['cost']['actions'], 1, 3)
        integer(event['cost']['money'], 0, 100000)
        fields = flatten(event['text']) if event['text'] is not None else {}
        assert event['status'] != 'ready' or fields, 'Ready event requires complete prose'
        variants = {}
        for variant in event['variants']:
            assert set(variant) == {'profile', 'overrides'}
            assert variant['profile'] in profiles and variant['profile'] not in variants
            assert fields and variant['overrides'] and set(variant['overrides']) <= set(fields)
            variants[variant['profile']] = {k: prose(v) for k, v in variant['overrides'].items()}
            for key in variant['overrides']:
                if key.endswith('_label'):
                    assert len(variant['overrides'][key]) == 1
        compiled[event['id']] = (fields, variants)
    lookup = {e['id']: e for e in events}
    for event in events:
        seen = {event['id']}
        current = event
        while current['requires_event']:
            prerequisite = current['requires_event']
            assert prerequisite in lookup and prerequisite not in seen, 'Missing or circular prerequisite'
            seen.add(prerequisite)
            current = lookup[prerequisite]
        if event['requires_choice']:
            predecessor = lookup[event['requires_event']]
            assert predecessor['text'] is not None
            trail = event['requires_choice']
            assert 1 <= trail // 10 <= len(predecessor['text']['rounds'][0]['choices'])
            assert 1 <= trail % 10 <= len(predecessor['text']['rounds'][1]['choices'])

    lines = ['; Generated by tools/build_interactions.py; edit JSON source instead.',
             '@IX_RULE(IX_E, IX_K)', '#FUNCTION', '#DIM DYNAMIC IX_E', '#DIM DYNAMIC IX_K', 'SELECTCASE IX_E']
    for event in events:
        values = [int(event['status'] == 'ready'), int(event['repeatable']), event['min_trust'],
                  event['requires_event'], event['requires_choice'], event['cost']['actions'], event['cost']['money']]
        lines += [f'CASE {event["id"]}', '\tSELECTCASE IX_K']
        for k, value in enumerate(values):
            lines += [f'\tCASE {k}', f'\t\tRETURNF {value}']
        lines += ['\tENDSELECT']
    lines += ['ENDSELECT', 'RETURNF -1', '', '@IX_MATCH(IX_P, IX_E)', '#FUNCTION',
              '#DIM DYNAMIC IX_P', '#DIM DYNAMIC IX_E', 'SELECTCASE IX_E']
    for event in events:
        lines += [f'CASE {event["id"]}']
        for key, expr in [('locations', 'CASTLE_STATE:2'), ('profiles', 'DIALOGUE_PROFILE(IX_P)'),
                          ('temperaments', 'DIALOGUE_PERSON:IX_P:DP_TEMPER'), ('origins', 'DIALOGUE_PERSON:IX_P:DP_ORIGIN')]:
            if event[key]:
                condition = ' && '.join(f'{expr} != {x}' for x in event[key])
                lines += [f'\tSIF {condition}', '\t\tRETURNF 0']
        lines += ['\tRETURNF 1']
    lines += ['ENDSELECT', 'RETURNF 0', '', '@IX_TITLE(IX_E)', '#FUNCTIONS', '#DIM DYNAMIC IX_E', 'SELECTCASE IX_E']
    for event in events:
        lines += [f'CASE {event["id"]}', '\tRETURNF ' + literal(event['title'])]
    lines += ['ENDSELECT', 'RETURNF ""', '', '@IX_CHOICES(IX_E, IX_R)', '#FUNCTION',
              '#DIM DYNAMIC IX_E', '#DIM DYNAMIC IX_R', 'SELECTCASE IX_E * 10 + IX_R']
    for event in events:
        if event['text'] is not None:
            for rnd, node in enumerate(event['text']['rounds'], 1):
                lines += [f'CASE {event["id"] * 10 + rnd}', f'\tRETURNF {len(node["choices"])}']
    lines += ['ENDSELECT', 'RETURNF 0', '', '@IX_EFFECT(IX_E, IX_R, IX_C, IX_KIND)', '#FUNCTION',
              '#DIM DYNAMIC IX_E', '#DIM DYNAMIC IX_R', '#DIM DYNAMIC IX_C', '#DIM DYNAMIC IX_KIND',
              'SELECTCASE IX_E * 100 + IX_R * 10 + IX_C']
    for event in events:
        if event['text'] is not None:
            for rnd, node in enumerate(event['text']['rounds'], 1):
                for pick, choice in enumerate(node['choices'], 1):
                    lines += [f'CASE {event["id"] * 100 + rnd * 10 + pick}',
                              f'\tRETURNF IX_KIND == 0 ? {choice["trust"]} # {choice["affection"]}']
    lines += ['ENDSELECT', 'RETURNF 0', '', '@IX_TEXT(IX_P, IX_E, IX_K, IX_LINE)', '#FUNCTIONS',
              '#DIM DYNAMIC IX_P', '#DIM DYNAMIC IX_E', '#DIM DYNAMIC IX_K', '#DIM DYNAMIC IX_LINE', 'SELECTCASE IX_E']

    def emit_fields(fields, indent):
        result = [indent + 'SELECTCASE IX_K * 100 + IX_LINE']
        for key, sentences in fields.items():
            for number, sentence in enumerate(sentences):
                result += [indent + f'CASE {field_id(key) * 100 + number}', indent + '\tRETURNF ' + literal(sentence)]
        return result + [indent + 'ENDSELECT']

    for event in events:
        fields, variants = compiled[event['id']]
        lines += [f'CASE {event["id"]}']
        for profile, overrides in variants.items():
            lines += [f'\tIF DIALOGUE_PROFILE(IX_P) == {profile}'] + emit_fields(overrides, '\t\t')
            # An override replaces the entire field, even when it has fewer lines.
            keys = ' || '.join(f'IX_K == {field_id(k)}' for k in overrides)
            lines += [f'\t\tSIF {keys}', '\t\t\tRETURNF ""', '\tENDIF']
        lines += emit_fields(fields, '\t')
    lines += ['ENDSELECT', 'RETURNF ""', '']
    return '\r\n'.join(lines).encode('utf-8-sig'), data


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    code, data = compile_interactions()
    if args.check:
        assert OUTPUT.read_bytes() == code, 'Regenerate interaction tables'
    else:
        OUTPUT.write_bytes(code)
    print(f'PASS: {len(data["events"])} castle interactions; drafts remain non-executable')
