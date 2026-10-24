"""Build isolated interaction fixtures; never copy or modify player saves."""
import argparse
import copy
import json
from pathlib import Path
import shutil
from check_castle import ROOT, check_sources, prepare
from build_interactions import SOURCE, compile_interactions


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('destination', type=Path)
    parser.add_argument('--load-save', type=Path)
    parser.add_argument('--filled-draft', action='store_true', help='Publish a copy of sample prose into the external fixture only')
    args = parser.parse_args()
    check_sources()
    prepare(args.destination, identity=True)
    data = json.loads(SOURCE.read_text(encoding='utf-8-sig'))
    paid = copy.deepcopy(data['events'][0])
    paid.update(id=3, key='fixture_paid', title='Fixture paid event', min_trust=3,
                requires_event=1, requires_choice=11, repeatable=False,
                cost={'actions': 1, 'money': 25})
    data['events'].append(paid)
    if args.filled_draft:
        assert args.load_save, 'Publication test resumes a known synthetic save'
        data['events'][1]['status'] = 'ready'
        data['events'][1]['text'] = copy.deepcopy(data['events'][0]['text'])
    (args.destination / 'ERB/INTERACTION_TEXT.ERB').write_bytes(compile_interactions(data)[0])
    title = args.destination / 'ERB/TITLE.ERB'
    old = title.read_text(encoding='utf-8-sig')
    fixture = (ROOT / 'tests/interaction_engine.ERB.txt').read_text(encoding='utf-8-sig')
    code = fixture + '\n' + old[old.index('@CT_ASSERT'):]
    if args.load_save:
        shutil.copy2(args.load_save, args.destination / 'sav/save98.sav')
        code = '''@SYSTEM_TITLE
LOADDATA 98

@IX_TEST_LOAD
CALL CASTLE_SYNC
CALL CT_ASSERT(INTERACTION_COUNT:1:1 == 2 && INTERACTION_CHOICE:1:1 == 22, "native save restores interaction choices and count")
CALL CT_ASSERT(INTERACTION_LAST:1:1 == DAY * 2 + TIME + 1, "native save restores cooldown")
CALL CT_ASSERT(IX_REASON(1, 1) == 6, "loading cannot repeat the same interaction period")
CALL CT_ASSERT(INTERACTION_COUNT:1:2 == 0 && IX_REASON(1, 2) == 10, "native save preserves missing-text placeholder without fake completion")
PRINTL INTERACTION LOAD ASSERTIONS PASSED
OUTPUTLOG
QUIT
''' + old[old.index('@CT_ASSERT'):]
        if args.filled_draft:
            start = code.index('CALL CT_ASSERT(INTERACTION_COUNT:1:2')
            end = code.index('PRINTL INTERACTION LOAD ASSERTIONS PASSED', start)
            code = code[:start] + '''DAY += 1
CALL CASTLE_SYNC
CASTLE_STATE:2 = CASTLE_WHERE(1)
CALL CT_ASSERT(IX_REASON(1, 2) == 0, "filled JSON draft becomes playable through the same compiler")
CT_QUEUE = 2, 2
CT_POS = 0
CT_SIZE = 2
CALL IX_PLAY(1, 2)
CALL CT_ASSERT(RESULT == 1 && INTERACTION_COUNT:1:2 == 1 && INTERACTION_CHOICE:1:2 == 22, "published draft completes through real menu input and persists choices")
CALL CT_ASSERT(IX_REASON(1, 2) == 5, "non-repeatable published event cannot be completed twice")
''' + code[end:]
        system = args.destination / 'ERB/SYSTEM.ERB'
        source = system.read_text(encoding='utf-8-sig')
        system.write_bytes(source.replace('@EVENTLOAD', '@EVENTLOAD\nCALL IX_TEST_LOAD', 1).replace('\n', '\r\n').encode('utf-8-sig'))
    title.write_bytes(code.replace('\n', '\r\n').encode('utf-8-sig'))
    print('Interaction fixture ready; scripted input and waits exist only in the external copy.')
