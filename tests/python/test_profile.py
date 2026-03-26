"""Tests for profile pipeline and profile output modules."""

import json
import os
import sys
import tempfile
import shutil
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'get-shit-done', 'bin'))

from lib_py.profile_pipeline import (
    _format_bytes, _is_genuine_user_message, _truncate_content,
    _is_log_heavy,
)
from lib_py.profile_output import (
    DIMENSION_KEYS, PROFILING_QUESTIONS, CLAUDE_INSTRUCTIONS,
    extract_section_content, build_section, update_section,
    detect_manual_edit, generate_workflow_section,
)


class TestFormatBytes(unittest.TestCase):
    def test_bytes(self):
        self.assertEqual(_format_bytes(500), '500 B')

    def test_kilobytes(self):
        result = _format_bytes(2048)
        self.assertIn('KB', result)

    def test_megabytes(self):
        result = _format_bytes(5 * 1024 * 1024)
        self.assertIn('MB', result)


class TestIsGenuineUserMessage(unittest.TestCase):
    def test_valid_message(self):
        record = {
            'type': 'user',
            'userType': 'external',
            'message': {'content': 'Hello'},
        }
        self.assertTrue(_is_genuine_user_message(record))

    def test_rejects_assistant(self):
        record = {
            'type': 'assistant',
            'userType': 'external',
            'message': {'content': 'Hello'},
        }
        self.assertFalse(_is_genuine_user_message(record))

    def test_rejects_meta(self):
        record = {
            'type': 'user',
            'userType': 'external',
            'isMeta': True,
            'message': {'content': 'Hello'},
        }
        self.assertFalse(_is_genuine_user_message(record))

    def test_rejects_local_command(self):
        record = {
            'type': 'user',
            'userType': 'external',
            'message': {'content': '<local-command>exit</local-command>'},
        }
        self.assertFalse(_is_genuine_user_message(record))


class TestTruncateContent(unittest.TestCase):
    def test_short_text(self):
        self.assertEqual(_truncate_content('short', 100), 'short')

    def test_long_text(self):
        result = _truncate_content('x' * 200, 100)
        self.assertEqual(len(result), 100 + len('... [truncated]'))
        self.assertTrue(result.endswith('[truncated]'))


class TestIsLogHeavy(unittest.TestCase):
    def test_log_heavy(self):
        lines = '\n'.join(['2026-01-01 INFO test'] * 10 + ['normal'])
        self.assertTrue(_is_log_heavy(lines))

    def test_not_log_heavy(self):
        self.assertFalse(_is_log_heavy('Normal content here'))

    def test_short_content(self):
        self.assertFalse(_is_log_heavy('Hi'))


class TestDimensionKeys(unittest.TestCase):
    def test_has_eight_dimensions(self):
        self.assertEqual(len(DIMENSION_KEYS), 8)

    def test_questions_match_dimensions(self):
        q_dims = {q['dimension'] for q in PROFILING_QUESTIONS}
        self.assertEqual(q_dims, set(DIMENSION_KEYS))

    def test_instructions_cover_dimensions(self):
        for dim in DIMENSION_KEYS:
            self.assertIn(dim, CLAUDE_INSTRUCTIONS)


class TestSectionManagement(unittest.TestCase):
    def test_build_section(self):
        result = build_section('test', 'source.md', 'Content here')
        self.assertIn('GSD:test-start', result)
        self.assertIn('GSD:test-end', result)
        self.assertIn('Content here', result)

    def test_extract_section_content(self):
        text = '<!-- GSD:profile-start source="a.json" -->\nProfile data\n<!-- GSD:profile-end -->'
        result = extract_section_content(text, 'profile')
        self.assertEqual(result, 'Profile data')

    def test_extract_returns_none_if_missing(self):
        result = extract_section_content('No sections here', 'profile')
        self.assertIsNone(result)

    def test_update_section_replaces(self):
        existing = 'Before\n<!-- GSD:test-start -->\nOld\n<!-- GSD:test-end -->\nAfter'
        result = update_section(existing, 'test', 'New content')
        self.assertEqual(result['action'], 'replaced')
        self.assertIn('New content', result['content'])
        self.assertNotIn('Old', result['content'])

    def test_update_section_appends(self):
        existing = 'Just content'
        result = update_section(existing, 'test', 'New section')
        self.assertEqual(result['action'], 'appended')
        self.assertIn('New section', result['content'])

    def test_detect_manual_edit_unchanged(self):
        content = '<!-- GSD:test-start -->\nOriginal\n<!-- GSD:test-end -->'
        self.assertFalse(detect_manual_edit(content, 'test', 'Original'))

    def test_detect_manual_edit_changed(self):
        content = '<!-- GSD:test-start -->\nEdited by user\n<!-- GSD:test-end -->'
        self.assertTrue(detect_manual_edit(content, 'test', 'Original'))


class TestGenerateWorkflowSection(unittest.TestCase):
    def test_returns_content(self):
        result = generate_workflow_section()
        self.assertFalse(result['hasFallback'])
        self.assertIn('GSD', result['content'])


if __name__ == '__main__':
    unittest.main()
