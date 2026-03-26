"""Tests for new state functions — begin-phase, signal-waiting, signal-resume."""

import json
import os
import sys
import tempfile
import shutil
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'get-shit-done', 'bin'))

from lib_py.state import state_extract_field


class TestStateExtractField(unittest.TestCase):
    def test_bold_format(self):
        content = '**Status:** Executing phase 3\n**Current Phase:** 3'
        self.assertEqual(state_extract_field(content, 'Status'), 'Executing phase 3')
        self.assertEqual(state_extract_field(content, 'Current Phase'), '3')

    def test_plain_format(self):
        content = 'Status: Active\nPhase: 1'
        self.assertEqual(state_extract_field(content, 'Status'), 'Active')

    def test_returns_none_if_missing(self):
        content = '**Status:** Active'
        self.assertIsNone(state_extract_field(content, 'Missing Field'))

    def test_case_insensitive(self):
        content = '**status:** active'
        self.assertEqual(state_extract_field(content, 'Status'), 'active')


class TestSignalWaitingResume(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.tmp, '.planning'))

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_signal_creates_waiting_json(self):
        from lib_py.state import cmd_signal_waiting
        with self.assertSystemExit():
            cmd_signal_waiting(self.tmp, 'decision', 'Which approach?', 'A|B', '3', False)
        wait_path = os.path.join(self.tmp, '.planning', 'WAITING.json')
        self.assertTrue(os.path.exists(wait_path))
        with open(wait_path) as f:
            data = json.load(f)
        self.assertEqual(data['status'], 'waiting')
        self.assertEqual(data['type'], 'decision')
        self.assertEqual(data['options'], ['A', 'B'])

    def test_resume_removes_waiting(self):
        wait_path = os.path.join(self.tmp, '.planning', 'WAITING.json')
        with open(wait_path, 'w') as f:
            json.dump({'status': 'waiting'}, f)

        from lib_py.state import cmd_signal_resume
        with self.assertSystemExit():
            cmd_signal_resume(self.tmp, False)
        self.assertFalse(os.path.exists(wait_path))

    def assertSystemExit(self):
        return self.assertRaises(SystemExit)


class TestBeginPhase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.tmp, '.planning'))
        state_content = '\n'.join([
            '---',
            'gsd_state_version: "1.0"',
            '---',
            '',
            '**Status:** Ready to execute',
            '**Current Phase:** 2',
            '**Current Phase Name:** Setup',
            '**Current Plan:** 1',
            '**Total Plans in Phase:** 2',
            '**Last Activity:** 2026-01-01',
            '**Last Activity Description:** Planned phase 2',
            '',
        ])
        with open(os.path.join(self.tmp, '.planning', 'STATE.md'), 'w') as f:
            f.write(state_content)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_updates_state_fields(self):
        from lib_py.state import cmd_state_begin_phase
        with self.assertRaises(SystemExit):
            cmd_state_begin_phase(self.tmp, '3', 'Build features', 4, False)

        with open(os.path.join(self.tmp, '.planning', 'STATE.md')) as f:
            content = f.read()

        self.assertIn('Executing phase 3', content)
        self.assertIn('**Current Phase:** 3', content)
        self.assertIn('Build features', content)
        self.assertIn('**Total Plans in Phase:** 4', content)


if __name__ == '__main__':
    unittest.main()
