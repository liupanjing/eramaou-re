"""Create an external original-engine fixture for the economy, without user saves."""
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
    fixture = (ROOT / 'tests/economy_engine.ERB.txt').read_text(encoding='utf-8-sig')
    code = fixture + '\n' + existing[existing.index('@CT_ASSERT'):]
    if args.load_save:
        shutil.copy2(args.load_save, args.destination / 'sav/save98.sav')
        code = '''@SYSTEM_TITLE
LOADDATA 98

@EF_AFTER_LOAD
#DIM DYNAMIC EF_MONEY
EF_MONEY = MONEY
CALL CASTLE_SYNC
CALL CT_ASSERT(EC_STATE:EC_VERSION == 1 && EC_STOCK:3 == 47, "native save preserves economy resources without migration refill")
CALL CT_ASSERT(EC_TECH:1 && EC_TECH:2 && EC_TECH:3 && EC_FACILITY_LEVEL(CL_FARM) == 2, "native save preserves completed research and construction")
CALL CT_ASSERT(EC_STATE:EC_BOOK_COUNT == 28 && EC_STATE:EC_DEBT == 0, "native save preserves ledger and arrears")
CALL CT_ASSERT(CASTLE_PERSON:1:CP_WORK == CL_FARM && MONEY == EF_MONEY, "load preserves new job and treasury")
CALL EC_SETTLE
CALL CT_ASSERT(RESULT == 0 && MONEY == EF_MONEY, "native save cannot repeat its already settled day")
DAY += 1
TIME = 0
CALL CASTLE_SYNC
CALL EC_CAPTURE_SHIFT
TIME = 1
CALL EC_SETTLE
CALL CT_ASSERT(RESULT == 1, "next uncompleted calendar day remains available after load")
EF_MONEY = MONEY
CALL EC_SETTLE
CALL CT_ASSERT(RESULT == 0 && MONEY == EF_MONEY, "native save prevents duplicate daily settlement")
PRINTL ECONOMY LOAD ASSERTIONS PASSED
OUTPUTLOG
QUIT
''' + existing[existing.index('@CT_ASSERT'):]
        system = args.destination / 'ERB/SYSTEM.ERB'
        source = system.read_text(encoding='utf-8-sig')
        system.write_bytes(source.replace('@EVENTLOAD', '@EVENTLOAD\nCALL EF_AFTER_LOAD', 1).replace('\n','\r\n').encode('utf-8-sig'))
    title.write_bytes(code.replace('\n', '\r\n').encode('utf-8-sig'))
    print('Economy fixture uses real transactions, production, attendance and tax settlement; no player saves copied.')
