"""Text handoffs must compile without changing mechanics or live game files."""
import copy
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import character_voice_handoff as handoff


class HandoffTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle, cls.sources = handoff.catalog()

    def selected(self, task_id):
        task = copy.deepcopy(next(t for t in self.bundle['tasks'] if t['id'] == task_id))
        task['draft'] = copy.deepcopy(task['current'])
        task['status'] = 'ready'
        return dict(schema_version=1, scope='non_graphic_only', tasks=[task]), task

    def test_export_covers_existing_sources_without_inventing_missing_text(self):
        self.assertEqual(len(self.bundle['profiles']), 29)
        self.assertEqual(len(self.bundle['tasks']), 723)
        self.assertEqual(len(self.bundle['legacy_inventory']), 19)
        for t in self.bundle['tasks']:
            self.assertEqual(t['current'], handoff.resolve(self.sources[t['target']['file']], t['target']['pointer']))
            self.assertIsNone(t['draft'])
        self.assertEqual(sum(t['mode'] == 'reference_only' for t in self.bundle['tasks']), 6)

    def test_current_bundle_compiles_to_identical_erb(self):
        sources, ready = handoff.prepare(self.bundle)
        self.assertEqual(ready, [])
        for file, value in handoff.compile_candidates(sources).items():
            self.assertEqual((ROOT / file).read_bytes(), value, file)

    def test_text_update_and_variant_extension_compile(self):
        bundle, t = self.selected('VOICE-170-daily')
        t['draft']['0'].append('「先听你把话说完。」{name}仍保留着自己的判断。')
        sources, ready = handoff.prepare(bundle)
        self.assertEqual(ready, [t['id']])
        self.assertIn('先听你把话说完', handoff.compile_candidates(sources)['ERB/DIALOGUE_VOICES.ERB'].decode('utf-8-sig'))
        self.assertNotEqual(sources['content/character_voices.json'], self.sources['content/character_voices.json'])

    def test_unready_draft_is_checked_but_not_merged(self):
        bundle, t = self.selected('VOICE-170-intro')
        t['status'] = 'draft'
        t['draft']['0'] = ['「先说说你的来意。」']
        sources, ready = handoff.prepare(bundle)
        self.assertEqual(ready, [])
        self.assertEqual(sources, self.sources)

    def test_invalid_inputs_are_rejected(self):
        cases = [
            ('VOICE-170-intro', lambda t: t['target'].update(file='../../outside.json')),
            ('VOICE-170-intro', lambda t: t.update(baseline_sha256='stale')),
            ('VOICE-170-intro', lambda t: t['draft'].update({'0': ['{unknown}']})),
            ('VOICE-170-intro', lambda t: t['draft'].update({'0': ['first\nCALL SOMETHING']})),
            ('VOICE-170-intro', lambda t: t['draft'].update({'0': ['__MASTER_NAME__']})),
            ('VOICE-170-intro', lambda t: t['draft'].pop('3')),
            ('EVENT-170-rest', lambda t: t['draft'].update({'0': ['only one variant']})),
            ('EVENT-165-join', lambda t: None),
            ('STORY-10-1', lambda t: t['draft']['first'][0].update(trust=999)),
            ('STORY-10-1', lambda t: t['draft']['first'].pop()),
        ]
        for task_id, mutate in cases:
            with self.subTest(task=task_id, mutation=mutate):
                bundle, task = self.selected(task_id)
                mutate(task)
                with self.assertRaises(ValueError):
                    handoff.prepare(bundle)
        bundle, task = self.selected('VOICE-170-intro')
        bundle['tasks'].append(copy.deepcopy(task))
        with self.assertRaises(ValueError):
            handoff.prepare(bundle)

    def test_story_text_changes_preserve_effects(self):
        bundle, t = self.selected('STORY-10-1')
        t['draft']['title'] = '测试用的回顾标题'
        sources, ready = handoff.prepare(bundle)
        self.assertEqual(ready, ['STORY-10-1'])
        compiled = handoff.compile_candidates(sources)['ERB/DIALOGUE_STORIES.ERB']
        self.assertIn('测试用的回顾标题', compiled.decode('utf-8-sig'))
        for field in ('first', 'second'):
            self.assertEqual([(c['trust'], c['agree']) for c in t['draft'][field]],
                             [(c['trust'], c['agree']) for c in t['current'][field]])

    def test_cli_stages_outside_game_without_touching_live_sources(self):
        files = [ROOT / file for file in self.sources] + [ROOT / file for file in handoff.compile_candidates(self.sources)]
        before = {p: p.read_bytes() for p in files}
        bundle, t = self.selected('EVENT-170-rest')
        t['draft']['0'][0] = '「你先歇一会儿吧。」'
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            input_file = root / 'tasks.json'
            input_file.write_bytes(handoff.encode(bundle))
            output = root / 'review'
            result = subprocess.run([sys.executable, str(ROOT / 'tools/character_voice_handoff.py'),
                                     '--stage', str(input_file), '--output-dir', str(output)], capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(len(list((output / 'content').glob('*.json'))), 4)
            self.assertEqual(len(list((output / 'ERB').glob('*.ERB'))), 3)
            report = handoff.read(output / 'handoff_result.json')
            self.assertEqual(report['ready_tasks'], ['EVENT-170-rest'])
            retry = subprocess.run([sys.executable, str(ROOT / 'tools/character_voice_handoff.py'),
                                    '--stage', str(input_file), '--output-dir', str(output)], capture_output=True)
            self.assertNotEqual(retry.returncode, 0)
        self.assertEqual(before, {p: p.read_bytes() for p in files})

    def test_cli_exports_per_character_and_never_overwrites_authors_file(self):
        with tempfile.TemporaryDirectory() as dirname:
            dest = Path(dirname) / 'one-character.json'
            cmd = [sys.executable, str(ROOT / 'tools/character_voice_handoff.py'),
                   '--export', str(dest), '--owner', '170']
            result = subprocess.run(cmd, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            bundle = handoff.read(dest)
            self.assertEqual({p['id'] for p in bundle['profiles']}, {170})
            self.assertEqual(len(bundle['tasks']), 27)
            self.assertEqual({t['owner'] for t in bundle['tasks']}, {170})
            handoff.prepare(bundle)
            before = dest.read_bytes()
            result = subprocess.run(cmd, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(dest.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
