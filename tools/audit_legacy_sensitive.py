"""Generate metadata-only indexes of known legacy sensitive-content areas.

No prose extraction, writing slots, runtime edits or event activation.
"""
import argparse
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'docs/legacy_sensitive_inventory.json'
GUIDE = ROOT / 'docs/遗留敏感内容索引.md'
GROUPS = [
    ('LEGACY-01', '旧指令实现', ['COMF*.ERB'], [],
     '指令文件包含敏感正文，也包含会话、等待等非露骨指令，不能整批视为缺文。'),
    ('LEGACY-02', '角色开始与结束反应', [], ['EVENTTRAIN', 'EVENTEND'],
     '混合普通开场和敏感分支；同名函数还承担口上开关管理。'),
    ('LEGACY-03', '角色指令反馈', [], ['KOJO_MESSAGE_COM_'],
     '已有大量正文；各指令和条件分支是否完整尚未逐项核验。'),
    ('LEGACY-04', '角色属性与刻印变化', [], ['KOJO_MESSAGE_PALAMCNG_', 'KOJO_MESSAGE_MARKCNG_'],
     '同一函数混合普通状态变化与敏感反应，不能一律标记为露骨。'),
    ('LEGACY-05', '角色独立反应及辅助函数', [], ['SELF_KOJO_', 'DOG_KOJO_', 'GOBI_KOUJO_', 'AEGI_', 'KOJO_MESSAGE_SYASEI_'],
     '包含条件反应、语尾和返回字符串辅助逻辑；没有PRINT不能作为空壳证据。'),
    ('LEGACY-06', '共用开始与过程描述', ['EVENT_BEFORETRAIN.ERB', 'EVENT_TRAIN_MESSAGE_A.ERB', 'EVENT_TRAIN_MESSAGE_B.ERB'], [],
     '共用描述与角色专属反馈分属不同入口。'),
    ('LEGACY-07', '结束后及自动事件', ['EVENT_AFTERTRAIN.ERB', 'EVENT_AUTOTRAIN.ERB', 'EVENT_ADDICT.ERB'], [],
     '包含敏感事件与普通清理、恢复、格式化逻辑；身份限制不能靠正文替代。'),
    ('LEGACY-08', '战后敏感分支', ['DUNGEON_AFTER.ERB'],
     ['DUNGEON_RYOUZYOKU_', 'DUNGEON_RYOUZYOKU_AFTER_', 'GOHOUBI_REQUEST_KOUJO_', 'GOHOUBI_AFTER_KOUJO_', 'OSIOKI_KOUJO_'],
     '入口与角色反应分别登记；攻击和胜利的非露骨新口上不属于此项。'),
    ('LEGACY-09', '旧特殊状态模块', ['BENKI.ERB', 'NAEDOKO.ERB'], ['BENKI_KOUJO_'],
     '保留原作实现和状态登记；未逐场核验。'),
    ('LEGACY-10', '第三方关系事件', ['NTR.ERB'], ['NTR_KOUJO_'],
     '包含正文与状态处理；不能从文件存在推断全部路线可达。'),
    ('LEGACY-11', '婚后与伴侣日常的敏感分支', ['MARRIAGE_DAY.ERB'], [],
     '混合普通生活与敏感分支，不把所有婚姻或家庭内容当作露骨。'),
    ('LEGACY-12', '旧定期特殊活动', ['EVENT_SABBATH.ERB'], [],
     '沿用旧事件；未逐场核验。'),
    ('LEGACY-13', '旧录像与经营相关正文', ['SELL_VIDEO.ERB'], [],
     '包含正文、结算和菜单；敏感正文与普通财务逻辑分开看待。'),
    ('LEGACY-14', '处置与特殊结局分支',
     ['EXECUTION.ERB', 'PUBLIC_EXECUTION.ERB', 'MUSEUM.ERB', 'BANISHMENT.ERB', 'GROTESQUE.ERB', 'SELL_MATURO*.ERB'],
     ['EXUCUTION_KOUJO_', 'MUSEUM_KOUJO_', 'BANISHMENT_KOUJO_', 'PUBLIC_EXUCUTION_KOUJO_', 'GROTESQUE_KOUJO_'],
     '混有暴力、恐怖及普通处置，不能将这些函数全部断言为性描写。'),
    ('LEGACY-15', '个人结局及追加结局', ['ENDINGDATA.ERB', 'ENDINGDATA_ADDON1.ERB'], [],
     '包含普通剧情和敏感段落；需要按具体结局核验，不是每个结局都缺失或露骨。'),
    ('LEGACY-16', '日期与生育相关混合处理', ['EVENT_NEXTDAY.ERB', 'EVENT_NEXTMONTH.ERB', 'EVENT_PREGNANCY.ERB', 'NINSIN.ERB'], [],
     '包含普通出生、照护及日期处理，只登记需区分的混合区域，不将生育本身标记为露骨。'),
    ('LEGACY-17', '旧中央分发与未接通入口', ['EVENT_K.ERB'], [],
     '中央分发主要是路由而非场景正文；主角、助手及切换的部分调用被注释，不能通过补文自动接通。'),
]


def inventory():
    coverage = json.loads((ROOT / 'docs/character_coverage.json').read_text(encoding='utf-8'))
    legacy = coverage['retained_legacy']
    areas = []
    for key, name, patterns, prefixes, note in GROUPS:
        files = sorted({p for pattern in patterns for p in (ROOT / 'ERB').glob(pattern)})
        references = []
        for path in files:
            text = path.read_text(encoding='utf-8-sig', errors='replace')
            references.append(dict(file=path.relative_to(ROOT).as_posix(),
                declarations=[dict(function=m.group(1), line=text.count('\n', 0, m.start()) + 1)
                              for m in re.finditer(r'^@([^\s(,]+)', text, re.M)]))
        character_entries = []
        for file in legacy:
            sections = [{k: s[k] for k in ('function', 'line', 'static_prints', 'status')}
                        for s in file['sections'] if any(s['function'].startswith(prefix) for prefix in prefixes)]
            if sections:
                character_entries.append(dict(file=file['file'], sections=sections))
        areas.append(dict(id=key, name=name, mode='inventory_only',
                          status='retained_not_fully_audited', authoring_enabled=False,
                          note=note, shared_files=references, character_entries=character_entries))
    report = dict(schema_version=1, mode='inventory_only', authoring_enabled=False,
        scope='已识别的遗留敏感与混合内容区域；按文件及函数索引，不是新增场景写作清单。',
        completeness='未穷尽全项目所有文本和运行分支；不得据此宣称所有露骨场景已逐一定位。',
        caveats=['有文件、有PRINT不等于条件分支齐全或实际可达。',
                 '旧角色文件也含非露骨反应，不应整体归类为露骨。',
                 '涉及年幼角色的遗留文件仅作审计登记，不作为成人创作任务；现有保护保持。',
                 '不提供敏感正文、续写提纲或可导入的成人草稿字段。'],
        areas=areas, character_files=[dict(file=f['file'], section_count=len(f['sections'])) for f in legacy],
        details_reference='docs/character_coverage.json',
        separate_non_graphic_tasks='content/character_voice_tasks.json')
    lines = ['# 遗留敏感内容索引', '',
        '2026年10月18日登记。本文按现有代码列出已识别的敏感及混合内容区域，供定位、审计与范围划分使用。配套机器索引为 [legacy_sensitive_inventory.json](legacy_sensitive_inventory.json)。', '',
        '这不是新增露骨场景的创作任务包，也不是已确认缺文表。已有文本是否需要修补，仍须核验具体分支与实际调用。未穷尽全项目的全部文本和运行路径，不能称作所有场景均已逐一确认。', '',
        '## 已识别区域', '',
        '| 编号 | 范围 | 代码位置 | 状态与说明 |',
        '| --- | --- | --- | --- |']
    for a, definition in zip(areas, GROUPS):
        location = '、'.join('`ERB/' + pattern + '`' for pattern in definition[2])
        if definition[3]:
            location += ('；' if location else '') + '角色文件内 ' + '、'.join('`' + x + '*`' for x in definition[3])
        lines.append(f'| {a["id"]} | {a["name"]} | {location} | {a["note"]} |')
    lines += ['', '## 角色文件范围', '',
        '下列19份文件均为遗留索引，不代表每个函数都含露骨内容。玛奥、菲娅等年幼角色的文件只作历史审计，不能作为成人创作任务。没有专属文件的角色也不能据此认定通用回退或其他剧情文件里没有相关文本。', '',
        '| 文件 | 声明数量 |', '| --- | --- |']
    lines += [f'| `{f["file"]}` | {len(f["sections"])} |' for f in legacy]
    lines += ['', '## 与非露骨任务包的关系', '',
        '- 本索引不参与 `character_voice_handoff.py` 的草稿合并，没有 `draft` 写入槽。',
        '- 原有非露骨任务包的723项不变，未把它们改成成人任务。',
        '- 旧分发的身份覆盖、停用入口及阶段匹配问题保留在开发日志的 KOJO-001～009；这些问题不能仅靠替换正文解决。',
        '- 没有PRINT不等于空壳：开关函数、返回字符串及委托调用必须分别判断。',
        '- 普通战斗胜利、设施任命和结局的新增非露骨反应继续由新模块处理，不因旧文件仍有同名反应就视为仍在调用。', '',
        '逐函数行号见配套JSON和 [character_coverage.json](character_coverage.json)。刷新索引使用 `python tools/audit_legacy_sensitive.py`，一致性检查使用 `python tools/audit_legacy_sensitive.py --check`。', '']
    return ((json.dumps(report, ensure_ascii=False, indent=2) + '\n').encode('utf-8'),
            '\n'.join(lines).encode('utf-8'), report)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    data, guide, report = inventory()
    if args.check:
        assert OUTPUT.read_bytes() == data and GUIDE.read_bytes() == guide, 'Sensitive index is stale'
    else:
        OUTPUT.write_bytes(data)
        GUIDE.write_bytes(guide)
    print(f'PASS: {len(report["areas"])} legacy areas, {len(report["character_files"])} character files; metadata only')
