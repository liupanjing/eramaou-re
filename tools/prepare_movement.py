"""Build an external native fixture for character schedules and saved locations."""
import argparse
from pathlib import Path
import shutil
from check_castle import ROOT, check_sources, prepare

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('destination', type=Path)
    parser.add_argument('--load-save', type=Path)
    args = parser.parse_args()
    check_sources()
    prepare(args.destination, identity=True)
    title = args.destination / 'ERB/TITLE.ERB'
    existing = title.read_text(encoding='utf-8-sig')
    code = (ROOT / 'tests/movement_engine.ERB.txt').read_text(encoding='utf-8-sig')
    code += '\n' + existing[existing.index('@CT_ASSERT'):]
    if args.load_save:
        shutil.copy2(args.load_save, args.destination / 'sav/save98.sav')
        code = '''@SYSTEM_TITLE
LOADDATA 98

@CM_TEST_LOAD
#DIM DYNAMIC CM_TEST_ACTIONS
#DIM DYNAMIC CM_TEST_MONEY
CM_TEST_ACTIONS = CASTLE_STATE:5
CM_TEST_MONEY = MONEY
CALL CASTLE_SYNC
CALL CT_ASSERT(CM_PERSON:1:CM_STAMP == DAY * 2 + TIME + 1 && CASTLE_WHERE(1) == CL_BARRACKS, "native save restores exact current outing without relocating home")
CALL CT_ASSERT(CASTLE_PERSON:1:CP_HOME == CL_QUARTERS && CASTLE_PERSON:1:CP_WORK == CL_WORKSHOP, "native save preserves home and workplace independently")
CALL CT_ASSERT(CASTLE_STATE:5 == CM_TEST_ACTIONS && MONEY == CM_TEST_MONEY, "loading schedule does not charge or refill actions")
CALL CT_ASSERT(IX_REASON(1, 1) == 6 && INTERACTION_COUNT:1:1 == 1, "saved encounter and location share the same conversation cooldown")
PRINTL MOVEMENT LOAD ASSERTIONS PASSED
OUTPUTLOG
QUIT
''' + existing[existing.index('@CT_ASSERT'):]
        system = args.destination / 'ERB/SYSTEM.ERB'
        source = system.read_text(encoding='utf-8-sig')
        system.write_bytes(source.replace('@EVENTLOAD', '@EVENTLOAD\nCALL CM_TEST_LOAD', 1).replace('\n','\r\n').encode('utf-8-sig'))
    title.write_bytes(code.replace('\n', '\r\n').encode('utf-8-sig'))
    print('Movement fixture ready; no player saves copied.')
