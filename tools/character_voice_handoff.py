"""Export, validate and stage text-only character writing handoffs.

Never writes live content/ or ERB/; --stage creates a new review directory.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import tempfile

import build_character_events
import build_character_voices
import build_dialogue

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ROOT / 'content/character_voice_tasks.json'
FILES = ('character_voices.json', 'character_events.json',
         'character_stories.json', 'dialogue_sample.json')
VOICE_FIELDS = {
    'intro': '初次实际交谈', 'greeting': '再次来访', 'daily': '日常话题',
    'positive': '积极回应', 'neutral': '中性回应', 'negative': '消极回应',
    'address': '对魔王的称呼', 'voice': '不依赖旧经历的招呼',
    'delivery': '物资实际交付后的回应', 'reserved_greeting': '低信任部下招呼',
    'reserved_daily': '低信任部下日常',
}
PHASES = {'0': '抗拒被俘', '1': '仍有戒备', '2': '有条件合作', '3': '正式归顺'}
SOCIAL_ONLY = {165, 104}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':')).encode('utf-8')).hexdigest()


def resolve(data, pointer):
    for part in pointer.strip('/').split('/'):
        data = data[int(part)] if isinstance(data, list) else data[part]
    return data


def replace(data, pointer, value):
    parts = pointer.strip('/').split('/')
    parent = data
    for part in parts[:-1]:
        parent = parent[int(part)] if isinstance(parent, list) else parent[part]
    key = int(parts[-1]) if isinstance(parent, list) else parts[-1]
    parent[key] = copy.deepcopy(value)


def catalog(root=ROOT):
    sources = {'content/' + f: read(root / 'content' / f) for f in FILES}
    voices = sources['content/character_voices.json']['profiles']
    tasks = []
    profiles = []

    def add(task_id, kind, owner, title, file, pointer, conditions, mode='editable'):
        current = copy.deepcopy(resolve(sources[file], pointer))
        tasks.append(dict(id=task_id, kind=kind, owner=owner, title=title,
                          target=dict(file=file, pointer=pointer), mode=mode,
                          coverage='existing_text_not_branch_complete',
                          conditions=conditions, baseline_sha256=digest(current),
                          current=current, status='pending', draft=None, author='', notes=''))

    for i, p in enumerate(voices):
        profiles.append({k: copy.deepcopy(p[k]) for k in
                         ('id', 'name', 'kind', 'self', 'csv', 'ex', 'talents', 'evidence') if k in p})
        profiles[-1]['social_only'] = p['id'] in SOCIAL_ONLY
        for field, label in VOICE_FIELDS.items():
            conditions = ['四态字段必须保留；实际触发服从运行时代码。']
            if p['id'] in SOCIAL_ONLY:
                conditions.append('仅生活、学习、照护与普通交流，不创作成年归顺或亲密桥段。')
            if field == 'intro':
                conditions.append('是否初见由 DP_MET 独立记录，不能把阶段等同于见面次数。')
            if field.startswith('reserved_'):
                conditions.append('仅低信任部下覆盖分支；不能把部下身份改成俘虏。')
            add(f'VOICE-{p["id"]}-{field}', 'voice', p['id'], label,
                'content/character_voices.json', f'/profiles/{i}/{field}', conditions)

    event_data = sources['content/character_events.json']
    event_meta = {e['key']: e for e in event_data['events']}
    for i, p in enumerate(event_data['profiles']):
        for key in p['events']:
            event = event_meta[key]
            disabled = p['id'] in SOCIAL_ONLY and key in {'join', 'job', 'job_clear'}
            conditions = [event['hook'], '仅填写现有阶段，不扩充触发条件。',
                          '每态至少两条；城务和结局的第3态下标0是低信任保留语气，下标1起为通常部下语气。']
            if p['id'] in SOCIAL_ONLY:
                conditions.append('只作适龄的非性内容；不能用台词绕过年龄或身份检查。')
            if disabled:
                conditions.append('当前年龄限制不播放此事件；保留源结构，仅供覆盖登记，不接受草稿。')
            add(f'EVENT-{p["id"]}-{key}', 'event', p['id'], event['name'],
                'content/character_events.json', f'/profiles/{i}/events/{key}', conditions,
                'reference_only' if disabled else 'editable')

    for filename in ('dialogue_sample.json', 'character_stories.json'):
        file = 'content/' + filename
        for i, pack in enumerate(sources[file]['packs']):
            owner = 170 if pack['id'] == 10 else pack['id']
            if filename == 'dialogue_sample.json' and pack['id'] != 10:
                owner = 'common-' + str(pack['id'])
            for j, event in enumerate(pack['events']):
                add(f'STORY-{pack["id"]}-{j+1}', 'story', owner,
                    pack['name'] + '／' + event['title'], file, f'/packs/{i}/events/{j}',
                    ['保留四段顺序、两轮选择及每轮三个选项。',
                     '可编辑 title/body/bridge/ending 和 first/second 的 text/reply。',
                     '不得改变选项顺序及 trust/agree；新文字必须保留原选项立场与承诺，旧存档按选项编号回顾。',
                     '阶段3重谈旧事，不重新收费、交付物资或再次宣告加入。'])

    report = read(root / 'docs/character_coverage.json')
    legacy = [dict(file=f['file'], mode='inventory_only',
                   status='retained_not_fully_audited',
                   sections=[{k: s[k] for k in ('function', 'line', 'static_prints', 'status')}
                             for s in f['sections']]) for f in report['retained_legacy']]
    return dict(schema_version=1, scope='non_graphic_only',
                instructions='仅编辑任务的 status/draft/author/notes。draft 为完整目标对象，不是散文说明。current 是只读原文；ready 才参与校验与暂存。',
                phases=PHASES, placeholders=['{name}', '{master}', '{self}', '{address}'],
                profiles=profiles, event_types=event_data['events'], tasks=tasks,
                integration_backlog=[
                    dict(id='HOOK-ORIGIN', status='requires_integration',
                         source='ERB/DIALOGUE_DAILY.ERB:DIALOGUE_DAILY_ORIGIN',
                         need='普通人物出身日常当前硬编码；需先拆出文本接口，再增加性格与出身组合。'),
                    dict(id='HOOK-FAMILY', status='requires_integration',
                         source='ERB/DIALOGUE_DAILY.ERB:DIALOGUE_SOCIAL_SESSION',
                         need='普通家属生活话题及回应存在共用硬编码；新增独立模板需要先接入。'),
                    dict(id='HOOK-FAILURE', status='requires_integration',
                         source='tools/build_dialogue.py:compile_stories',
                         need='关键交涉失败结尾为共用句；人物专属失败、取消及中止反应需要新接口。'),
                    dict(id='HOOK-FACILITY', status='requires_integration',
                         source='ERB/ECONOMY.ERB',
                         need='设施经营、出勤、生产、建设与研究结算已实现；人物专属成果反应尚未拆出文本接口，不能直接混入旧事件。'),
                    dict(id='HOOK-MAINLINE', status='blocked_by_story_design',
                         need='狂王本尊主线、商路与忍者组织剧情需先明确流程与触发点，不混入现有可导入任务。'),
                ], legacy_inventory=legacy), sources


def sentence(value):
    require(isinstance(value, str) and bool(value.strip()), 'Text must be a nonempty string')
    rest = re.sub(r'\{(?:name|master|self|address)\}', '', value)
    require(not any(c in rest for c in '%{}') and not any(ord(c) < 32 for c in value),
            'Unsupported placeholder, control character or multiline text')
    require(not re.search(r'__[A-Z][A-Z_]*__', value), 'Use public placeholders, not internal runtime markers')


def state_lines(current, draft, minimum=1):
    require(isinstance(draft, dict) and set(draft) == set(current), 'Attitude keys changed')
    for lines in draft.values():
        require(isinstance(lines, list) and len(lines) >= minimum, 'Missing text variants')
        for line in lines:
            sentence(line)


def prose(current, draft):
    require(isinstance(draft, list) and len(draft) == len(current), 'Story prose structure changed')
    for old, new in zip(current, draft):
        if isinstance(old, str):
            sentence(new)
        else:
            state_lines(old, new)


def story(current, draft):
    require(isinstance(draft, dict) and set(draft) == set(current), 'Story event fields changed')
    sentence(draft['title'])
    for field in ('body', 'bridge', 'ending'):
        prose(current[field], draft[field])
    for field in ('first', 'second'):
        choices = draft[field]
        require(isinstance(choices, list) and len(choices) == 3, 'Three ordered choices required')
        for old, new in zip(current[field], choices):
            require(isinstance(new, dict) and set(new) == set(old), 'Choice fields changed')
            require(all(type(new[k]) is type(old[k]) and new[k] == old[k]
                        for k in old if k not in ('text', 'reply')), 'Choice effects changed or reordered')
            sentence(new['text'])
            prose(old['reply'], new['reply'])


def prepare(bundle, root=ROOT):
    require(isinstance(bundle, dict), 'Handoff must be a JSON object')
    require(bundle.get('schema_version') == 1 and bundle.get('scope') == 'non_graphic_only',
            'Unsupported handoff version or scope')
    expected, sources = catalog(root)
    known = {t['id']: t for t in expected['tasks']}
    tasks = bundle.get('tasks')
    require(isinstance(tasks, list) and bool(tasks), 'No task list')
    seen, ready = set(), []
    for task in tasks:
        require(isinstance(task, dict), 'Each task must be a JSON object')
        key = task.get('id')
        require(key in known and key not in seen, 'Unknown or duplicate task: ' + str(key))
        seen.add(key)
        spec = known[key]
        require(set(task) == set(spec), key + ': task fields changed')
        for field in ('kind', 'owner', 'title', 'target', 'mode', 'coverage', 'conditions'):
            require(task[field] == spec[field], key + ': protected metadata changed: ' + field)
        require(task['status'] in ('pending', 'draft', 'ready', 'deferred'), key + ': invalid status')
        require(isinstance(task['author'], str) and isinstance(task['notes'], str), key + ': invalid notes')
        require(task['mode'] == 'editable' or task['draft'] is None, key + ': reference-only task')
        require(task['status'] not in ('draft', 'ready') or task['draft'] is not None,
                key + ': draft/ready requires a complete draft')
        require(task['status'] != 'ready' or task['mode'] == 'editable', key + ': cannot import reference-only task')
        if task['draft'] is None:
            continue
        require(task['baseline_sha256'] == spec['baseline_sha256'] and
                digest(task['current']) == spec['baseline_sha256'], key + ': stale or edited baseline')
        value = task['draft']
        if spec['kind'] == 'story':
            story(spec['current'], value)
        else:
            state_lines(spec['current'], value, 2 if spec['kind'] == 'event' else 1)
        if task['status'] == 'ready':
            replace(sources[spec['target']['file']], spec['target']['pointer'], value)
            ready.append(key)
    return sources, ready


def encode(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8')


def compile_candidates(sources):
    with tempfile.TemporaryDirectory(prefix='eramaou-voices-') as dirname:
        stage = Path(dirname)
        (stage / 'content').mkdir()
        for file, value in sources.items():
            (stage / file).write_bytes(encode(value))
        outputs = {}
        for module, source, output, evidence_root in (
                (build_character_voices, 'character_voices.json', 'DIALOGUE_VOICES.ERB', ROOT),
                (build_character_events, 'character_events.json', 'CHARACTER_EVENTS_TEXT.ERB', stage),
                (build_dialogue, 'dialogue_sample.json', 'DIALOGUE_STORIES.ERB', stage)):
            old_root, old_source = module.ROOT, module.SOURCE
            try:
                module.ROOT, module.SOURCE = evidence_root, stage / 'content' / source
                outputs['ERB/' + output] = module.__dict__[
                    {'character_voices.json': 'compile_voices', 'character_events.json': 'compile_events',
                     'dialogue_sample.json': 'compile_stories'}[source]]()[0]
            finally:
                module.ROOT, module.SOURCE = old_root, old_source
    return outputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--export', type=Path, metavar='NEW_JSON')
    group.add_argument('--validate', type=Path, metavar='JSON')
    group.add_argument('--stage', type=Path, metavar='JSON')
    parser.add_argument('--owner', help='With --export: profile ID or common-0/common-1/common-2/common-3')
    parser.add_argument('--output-dir', type=Path, help='New review directory; required with --stage')
    args = parser.parse_args()
    try:
        if args.export:
            require(not args.output_dir, '--output-dir is only for --stage')
            bundle, _ = catalog()
            if args.owner:
                owner = int(args.owner) if args.owner.isdecimal() else args.owner
                bundle['tasks'] = [t for t in bundle['tasks'] if t['owner'] == owner]
                require(bool(bundle['tasks']), 'Unknown task owner')
                bundle['profiles'] = [p for p in bundle['profiles'] if
                                      p['id'] == owner or (isinstance(owner, str) and p['kind'] == 'personality')]
                evidence = {e['file'] for p in bundle['profiles'] for e in p['evidence']}
                bundle['legacy_inventory'] = [f for f in bundle['legacy_inventory'] if f['file'] in evidence]
            with args.export.open('xb') as stream:
                stream.write(encode(bundle))
            print(f'PASS: exported {len(bundle["profiles"])} profiles, {len(bundle["tasks"])} tasks; no existing file overwritten')
            return
        require(not args.owner, '--owner is only for --export')
        require(bool(args.stage) == bool(args.output_dir), 'Use --stage JSON --output-dir NEW_DIRECTORY')
        bundle = read(args.stage or args.validate)
        sources, ready = prepare(bundle)
        outputs = compile_candidates(sources)
        if args.stage:
            dest = args.output_dir.resolve()
            require(dest != ROOT and ROOT not in dest.parents, 'Review directory must be outside the game project')
            require(not dest.exists(), 'Review directory must not exist')
            dest.mkdir(parents=True)
            for file, value in sources.items():
                path = dest / file
                path.parent.mkdir(exist_ok=True)
                path.write_bytes(encode(value))
            for file, value in outputs.items():
                path = dest / file
                path.parent.mkdir(exist_ok=True)
                path.write_bytes(value)
            (dest / 'handoff_result.json').write_bytes(encode(dict(ready_tasks=ready,
                note='Review semantic consistency and original choice meanings before copying into the game.')))
        print(f'PASS: {len(bundle["tasks"])} tasks validated; {len(ready)} ready tasks; all three native generators passed; live game unchanged')
    except (ValueError, AssertionError, KeyError, TypeError, OSError) as exc:
        parser.exit(1, 'ERROR: ' + str(exc) + '\n')


if __name__ == '__main__':
    main()
