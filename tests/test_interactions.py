"""Authoring validation protects native execution and saved event identity."""
import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from build_interactions import SOURCE, OUTPUT, compile_interactions


class InteractionsTest(unittest.TestCase):
    def setUp(self):
        self.data = json.loads(SOURCE.read_text(encoding='utf-8-sig'))

    def test_generated_source_is_current(self):
        self.assertEqual(compile_interactions(self.data)[0], OUTPUT.read_bytes())

    def test_unfinished_event_cannot_be_published(self):
        self.data['events'][1]['status'] = 'ready'
        with self.assertRaises(AssertionError):
            compile_interactions(self.data)

    def test_complete_draft_can_be_published(self):
        self.data['events'][1]['text'] = copy.deepcopy(self.data['events'][0]['text'])
        self.data['events'][1]['status'] = 'ready'
        self.assertIn(b'CASE 2', compile_interactions(self.data)[0])

    def test_rejects_broken_prerequisites_and_choices(self):
        for event_id, choice in [(15, 0), (2, 0), (1, 33), (1, 10)]:
            with self.subTest(event_id=event_id, choice=choice):
                data = copy.deepcopy(self.data)
                data['events'][1]['requires_event'] = event_id
                data['events'][1]['requires_choice'] = choice
                with self.assertRaises(AssertionError):
                    compile_interactions(data)

    def test_rejects_prose_code_and_undefined_tokens(self):
        for line in ['%MONEY%', '{unknown}', 'a\nb', '__NPC_NAME__', '"', '\\', '\x00']:
            with self.subTest(line=line):
                data = copy.deepcopy(self.data)
                data['events'][0]['text']['opening'] = [line]
                with self.assertRaises(AssertionError):
                    compile_interactions(data)

    def test_rejects_invalid_costs_effects_and_duplicate_ids(self):
        for kind in ['cost', 'effect', 'id', 'location', 'override']:
            with self.subTest(kind=kind):
                data = copy.deepcopy(self.data)
                event = data['events'][0]
                if kind == 'cost':
                    event['cost']['actions'] = -1
                elif kind == 'effect':
                    event['text']['rounds'][0]['choices'][0]['trust'] = 100
                elif kind == 'id':
                    data['events'][1]['id'] = 1
                elif kind == 'location':
                    event['locations'] = [99]
                else:
                    event['variants'][0]['overrides']['unknown'] = ['test']
                with self.assertRaises(AssertionError):
                    compile_interactions(data)


if __name__ == '__main__':
    unittest.main()
