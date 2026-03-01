"""Tests for gsd-tools.py dispatcher — CLI integration tests."""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from helpers import run_gsd_tools, create_temp_project, create_temp_git_project, cleanup


class TestDispatcherBasics(unittest.TestCase):
    def test_no_args_shows_usage(self):
        result = run_gsd_tools([])
        self.assertFalse(result['success'])
        self.assertIn('Usage', result['error'])

    def test_unknown_command_errors(self):
        result = run_gsd_tools(['nonexistent-command'])
        self.assertFalse(result['success'])
        self.assertIn('Unknown command', result['error'])

    def test_generate_slug(self):
        result = run_gsd_tools(['generate-slug', 'Hello World'])
        self.assertTrue(result['success'])
        data = json.loads(result['output'])
        self.assertEqual(data['slug'], 'hello-world')

    def test_generate_slug_raw(self):
        result = run_gsd_tools(['generate-slug', 'Hello World', '--raw'])
        self.assertTrue(result['success'])
        self.assertEqual(result['output'], 'hello-world')

    def test_current_timestamp_date(self):
        result = run_gsd_tools(['current-timestamp', 'date'])
        self.assertTrue(result['success'])
        data = json.loads(result['output'])
        self.assertRegex(data['timestamp'], r'^\d{4}-\d{2}-\d{2}$')

    def test_current_timestamp_full(self):
        result = run_gsd_tools(['current-timestamp', 'full'])
        self.assertTrue(result['success'])
        data = json.loads(result['output'])
        self.assertIn('T', data['timestamp'])


class TestStateCLI(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = create_temp_project()

    def tearDown(self):
        cleanup(self.tmp_dir)

    def test_state_load_with_no_state_file(self):
        result = run_gsd_tools(['state', 'load'], cwd=self.tmp_dir)
        # Should succeed but indicate no state
        self.assertTrue(result['success'] or 'not found' in result['output'].lower() or 'error' in result['output'].lower())

    def test_state_load_with_state_file(self):
        state_path = os.path.join(self.tmp_dir, '.planning', 'STATE.md')
        with open(state_path, 'w') as f:
            f.write('---\nphase: 01\nstatus: active\n---\n\n# State\n\n**Current Phase:** 1\n**Status:** Active\n')
        result = run_gsd_tools(['state'], cwd=self.tmp_dir)
        self.assertTrue(result['success'])


class TestConfigCLI(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = create_temp_project()

    def tearDown(self):
        cleanup(self.tmp_dir)

    def test_config_ensure_creates_default(self):
        result = run_gsd_tools(['config-ensure-section'], cwd=self.tmp_dir)
        self.assertTrue(result['success'])
        data = json.loads(result['output'])
        self.assertTrue(data.get('created') or data.get('exists'))

    def test_config_set_and_get(self):
        run_gsd_tools(['config-ensure-section'], cwd=self.tmp_dir)
        run_gsd_tools(['config-set', 'model_profile', 'quality'], cwd=self.tmp_dir)
        result = run_gsd_tools(['config-get', 'model_profile'], cwd=self.tmp_dir)
        self.assertTrue(result['success'])
        data = json.loads(result['output'])
        self.assertEqual(data['value'], 'quality')


class TestCwdOverride(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = create_temp_project()

    def tearDown(self):
        cleanup(self.tmp_dir)

    def test_cwd_flag(self):
        result = run_gsd_tools(['config-ensure-section', '--cwd', self.tmp_dir])
        self.assertTrue(result['success'])

    def test_cwd_equals_flag(self):
        result = run_gsd_tools(['config-ensure-section', '--cwd=%s' % self.tmp_dir])
        self.assertTrue(result['success'])


class TestPhaseCLI(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = create_temp_project()
        phases_dir = os.path.join(self.tmp_dir, '.planning', 'phases')
        os.makedirs(os.path.join(phases_dir, '01-init'))
        os.makedirs(os.path.join(phases_dir, '02-setup'))

    def tearDown(self):
        cleanup(self.tmp_dir)

    def test_find_phase(self):
        result = run_gsd_tools(['find-phase', '1'], cwd=self.tmp_dir)
        self.assertTrue(result['success'])
        data = json.loads(result['output'])
        self.assertTrue(data['found'])
        self.assertEqual(data['phase_number'], '01')

    def test_phases_list(self):
        result = run_gsd_tools(['phases', 'list'], cwd=self.tmp_dir)
        self.assertTrue(result['success'])
        data = json.loads(result['output'])
        self.assertEqual(data['count'], 2)


if __name__ == '__main__':
    unittest.main()
