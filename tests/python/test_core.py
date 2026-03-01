"""Tests for lib_py/core.py — foundational utilities."""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'get-shit-done', 'bin'))

from lib_py.core import (
    load_config, resolve_model_internal, MODEL_PROFILES, escape_regex,
    generate_slug_internal, normalize_phase_name, compare_phase_num,
    safe_read_file, path_exists_internal, get_milestone_info,
    get_roadmap_phase_internal, find_phase_internal, _PhaseKey,
)
from helpers import create_temp_project, cleanup


class TestLoadConfig(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = create_temp_project()

    def tearDown(self):
        cleanup(self.tmp_dir)

    def _write_config(self, obj):
        with open(os.path.join(self.tmp_dir, '.planning', 'config.json'), 'w') as f:
            json.dump(obj, f)

    def test_defaults_when_missing(self):
        config = load_config(self.tmp_dir)
        self.assertEqual(config['model_profile'], 'balanced')
        self.assertTrue(config['commit_docs'])
        self.assertTrue(config['research'])

    def test_reads_model_profile(self):
        self._write_config({'model_profile': 'quality'})
        config = load_config(self.tmp_dir)
        self.assertEqual(config['model_profile'], 'quality')

    def test_reads_nested_config(self):
        self._write_config({'planning': {'commit_docs': False}})
        config = load_config(self.tmp_dir)
        self.assertFalse(config['commit_docs'])


class TestNormalizePhaseName(unittest.TestCase):
    def test_pads_single_digit(self):
        self.assertEqual(normalize_phase_name('3'), '03')

    def test_preserves_two_digit(self):
        self.assertEqual(normalize_phase_name('12'), '12')

    def test_handles_letter_suffix(self):
        self.assertEqual(normalize_phase_name('3A'), '03A')

    def test_handles_decimal(self):
        self.assertEqual(normalize_phase_name('3.1'), '03.1')


class TestComparePhaseNum(unittest.TestCase):
    def test_integer_ordering(self):
        self.assertLess(compare_phase_num('01', '02'), 0)
        self.assertGreater(compare_phase_num('10', '02'), 0)

    def test_decimal_ordering(self):
        self.assertLess(compare_phase_num('03.1', '03.2'), 0)
        self.assertLess(compare_phase_num('03.1', '04'), 0)

    def test_letter_suffix(self):
        self.assertLess(compare_phase_num('03', '03A'), 0)
        self.assertLess(compare_phase_num('03A', '04'), 0)

    def test_equal(self):
        self.assertEqual(compare_phase_num('03', '03'), 0)


class TestPhaseKey(unittest.TestCase):
    def test_sorting(self):
        dirs = ['03-setup', '01-init', '02-config', '01.1-hotfix']
        result = sorted(dirs, key=_PhaseKey)
        self.assertEqual(result[0], '01-init')
        self.assertEqual(result[1], '01.1-hotfix')
        self.assertEqual(result[2], '02-config')
        self.assertEqual(result[3], '03-setup')


class TestGenerateSlug(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(generate_slug_internal('Hello World'), 'hello-world')

    def test_special_chars(self):
        self.assertEqual(generate_slug_internal('foo@bar!baz'), 'foo-bar-baz')

    def test_collapse_dashes(self):
        self.assertEqual(generate_slug_internal('foo---bar'), 'foo-bar')


class TestEscapeRegex(unittest.TestCase):
    def test_escapes_special(self):
        self.assertEqual(escape_regex('3.1'), '3\\.1')
        self.assertEqual(escape_regex('a[b]'), 'a\\[b\\]')


class TestSafeReadFile(unittest.TestCase):
    def test_returns_none_for_missing(self):
        self.assertIsNone(safe_read_file('/nonexistent/path/file.txt'))

    def test_reads_existing_file(self):
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write('hello')
            path = f.name
        try:
            self.assertEqual(safe_read_file(path), 'hello')
        finally:
            os.unlink(path)


class TestFindPhaseInternal(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = create_temp_project()
        phases_dir = os.path.join(self.tmp_dir, '.planning', 'phases')
        os.makedirs(os.path.join(phases_dir, '01-init'))
        os.makedirs(os.path.join(phases_dir, '02-setup'))

    def tearDown(self):
        cleanup(self.tmp_dir)

    def test_finds_existing_phase(self):
        result = find_phase_internal(self.tmp_dir, '1')
        self.assertTrue(result['found'])
        self.assertEqual(result['phase_number'], '01')

    def test_returns_none_for_missing(self):
        result = find_phase_internal(self.tmp_dir, '99')
        self.assertTrue(result is None or not result.get('found'))


if __name__ == '__main__':
    unittest.main()
