"""Tests for workstream module — CRUD, migration, isolation."""

import json
import os
import sys
import tempfile
import shutil
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'get-shit-done', 'bin'))

from lib_py.workstream import (
    migrate_to_workstreams, _validate_ws_name, _get_active_workstream,
    _set_active_workstream, get_other_active_workstreams,
)


class TestValidateWsName(unittest.TestCase):
    def test_valid_name(self):
        self.assertTrue(_validate_ws_name('my-stream'))

    def test_rejects_slash(self):
        self.assertFalse(_validate_ws_name('a/b'))

    def test_rejects_dot(self):
        self.assertFalse(_validate_ws_name('.'))
        self.assertFalse(_validate_ws_name('..'))

    def test_rejects_empty(self):
        self.assertFalse(_validate_ws_name(''))
        self.assertFalse(_validate_ws_name(None))


class TestMigrateToWorkstreams(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.planning = os.path.join(self.tmp, '.planning')
        os.makedirs(self.planning)
        with open(os.path.join(self.planning, 'ROADMAP.md'), 'w') as f:
            f.write('# Roadmap')
        with open(os.path.join(self.planning, 'STATE.md'), 'w') as f:
            f.write('**Status:** Active')
        os.makedirs(os.path.join(self.planning, 'phases', '01-setup'), exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_migrates_files(self):
        result = migrate_to_workstreams(self.tmp, 'main')
        self.assertTrue(result['migrated'])
        self.assertEqual(result['workstream'], 'main')
        ws_dir = os.path.join(self.planning, 'workstreams', 'main')
        self.assertTrue(os.path.exists(os.path.join(ws_dir, 'ROADMAP.md')))
        self.assertTrue(os.path.exists(os.path.join(ws_dir, 'STATE.md')))
        self.assertTrue(os.path.isdir(os.path.join(ws_dir, 'phases')))
        self.assertFalse(os.path.exists(os.path.join(self.planning, 'ROADMAP.md')))

    def test_rejects_invalid_name(self):
        with self.assertRaises(ValueError):
            migrate_to_workstreams(self.tmp, '..')

    def test_rejects_if_already_workstream_mode(self):
        os.makedirs(os.path.join(self.planning, 'workstreams'))
        with self.assertRaises(ValueError):
            migrate_to_workstreams(self.tmp, 'main')


class TestActiveWorkstream(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.planning = os.path.join(self.tmp, '.planning')
        os.makedirs(os.path.join(self.planning, 'workstreams', 'test-ws'))

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_set_and_get(self):
        _set_active_workstream(self.tmp, 'test-ws')
        result = _get_active_workstream(self.tmp)
        self.assertEqual(result, 'test-ws')

    def test_clear(self):
        _set_active_workstream(self.tmp, 'test-ws')
        _set_active_workstream(self.tmp, None)
        result = _get_active_workstream(self.tmp)
        self.assertIsNone(result)

    def test_get_returns_none_if_dir_missing(self):
        _set_active_workstream(self.tmp, 'nonexistent')
        result = _get_active_workstream(self.tmp)
        self.assertIsNone(result)


class TestGetOtherActiveWorkstreams(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.planning = os.path.join(self.tmp, '.planning')
        ws_root = os.path.join(self.planning, 'workstreams')
        for name in ('alpha', 'beta', 'archived'):
            ws_dir = os.path.join(ws_root, name)
            os.makedirs(os.path.join(ws_dir, 'phases'), exist_ok=True)

        with open(os.path.join(ws_root, 'alpha', 'STATE.md'), 'w') as f:
            f.write('**Status:** Executing phase 3\n**Current Phase:** 3')
        with open(os.path.join(ws_root, 'beta', 'STATE.md'), 'w') as f:
            f.write('**Status:** Planning\n**Current Phase:** 1')
        with open(os.path.join(ws_root, 'archived', 'STATE.md'), 'w') as f:
            f.write('**Status:** Milestone complete\n**Current Phase:** Done')

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_excludes_specified_workstream(self):
        result = get_other_active_workstreams(self.tmp, 'alpha')
        names = [ws['name'] for ws in result]
        self.assertNotIn('alpha', names)
        self.assertIn('beta', names)

    def test_excludes_archived(self):
        result = get_other_active_workstreams(self.tmp, 'alpha')
        names = [ws['name'] for ws in result]
        self.assertNotIn('archived', names)


if __name__ == '__main__':
    unittest.main()
