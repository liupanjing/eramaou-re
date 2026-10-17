"""Create an isolated playable dialogue sample with the bundled Emuera engine."""
import argparse
from pathlib import Path
from check_castle import prepare, check_sources

TITLE = '''@SYSTEM_TITLE
#DIM DYNAMIC DD_I
RESETDATA
CALL CHARA_NAME_INIT
ADDCHARA 0
ADDCHARA 13
ADDCHARA 1
ADDCHARA 2
ADDCHARA 23
ADDCHARA 17
ADDCHARA 20
ADDCHARA 21
ADDCHARA 22
ADDCHARA 24
ADDCHARA 31
ADDCHARA 32
ADDCHARA 33
ADDCHARA 34
ADDCHARA 35
ADDCHARA 150
MASTER = 0
MONEY = 5000
ABL:0:15 = 3
TARGET = -1
ASSI = -1
BOUGHT = -1
PLAYER = 0
DAY:1 = 1
DAY:2 = 1
FLAG:5 = 17179934119
FLAG:7 = 2
FLAG:8 = 7
FLAG:26 = 232015325431115011
FLAG:27 = 001001
FLAG:500 = 2
FLAG:37 = 1
PBAND = 4
EX_FLAG:99 = 70
EX_FLAG:4444 = 1234
CALL EX_TALENTNAME_INIT
FOR DD_I, 0, CHARANUM
    CFLAG:DD_I:451 = 27
    SELECTCASE NO:DD_I
    CASE 17
        CFLAG:DD_I:451 = 12
    CASE 35
        CFLAG:DD_I:451 = 10
    CASE 20, 24
        CFLAG:DD_I:451 = 18
    CASE 21
        CFLAG:DD_I:451 = 24
    CASE 22, 150
        CFLAG:DD_I:451 = 21
    ENDSELECT
    CFLAG:DD_I:6 = 19000 + DD_I
    CFLAG:DD_I:1 = 0
    CFLAG:DD_I:2 = 0
    CFLAG:DD_I:10 = 0
    SAVESTR:DD_I = %NAME:DD_I%
NEXT
NAME:1 = 刚强的女骑士
TALENT:1:12 = 1
TALENT:1:315 = 19
NAME:2 = 胆怯的村民
TALENT:2:162 = 1
TALENT:2:315 = 3
NAME:3 = 冷静的学者
TALENT:3:164 = 1
TALENT:3:315 = 1
FOR DD_I, 0, CHARANUM
    SAVESTR:DD_I = %NAME:DD_I%
NEXT
CALL CASTLE_SYNC
CASTLE_STATE:2 = CL_DUNGEON
; 只准备样板人物。显示、输入与回合全部进入正式SHOP流程。
BEGIN SHOP
'''

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    check_sources()
    prepare(args.destination)
    target = args.destination.resolve()/'ERB/TITLE.ERB'
    target.write_bytes(TITLE.replace('\n', '\r\n').encode('utf-8-sig'))
    print('Playable sample ready; player saves are not copied.')
