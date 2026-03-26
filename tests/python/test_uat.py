"""Tests for UAT module — audit scanning, item parsing, checkpoints."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'get-shit-done', 'bin'))

from lib_py.uat import (
    categorize_item, parse_uat_items, parse_verification_items,
    parse_current_test, build_checkpoint,
)


class TestCategorizeItem(unittest.TestCase):
    def test_pending(self):
        self.assertEqual(categorize_item('pending'), 'pending')

    def test_blocked_server(self):
        self.assertEqual(categorize_item('blocked', blocked_by='server not running'), 'server_blocked')

    def test_blocked_device(self):
        self.assertEqual(categorize_item('blocked', blocked_by='physical device needed'), 'device_needed')

    def test_blocked_build(self):
        self.assertEqual(categorize_item('blocked', blocked_by='build not ready'), 'build_needed')

    def test_blocked_third_party(self):
        self.assertEqual(categorize_item('blocked', blocked_by='Stripe API'), 'third_party')

    def test_blocked_generic(self):
        self.assertEqual(categorize_item('blocked', blocked_by='something else'), 'blocked')

    def test_skipped_server(self):
        self.assertEqual(categorize_item('skipped', reason='server not available'), 'server_blocked')

    def test_skipped_unresolved(self):
        self.assertEqual(categorize_item('skipped', reason='some reason'), 'skipped_unresolved')

    def test_human_needed(self):
        self.assertEqual(categorize_item('human_needed'), 'human_uat')

    def test_unknown(self):
        self.assertEqual(categorize_item('other'), 'unknown')


class TestParseUatItems(unittest.TestCase):
    def test_parses_pending_item(self):
        content = """### 1. Setup project
expected: Directories created
result: pending
"""
        items = parse_uat_items(content)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['test'], 1)
        self.assertEqual(items[0]['name'], 'Setup project')
        self.assertEqual(items[0]['result'], 'pending')
        self.assertEqual(items[0]['category'], 'pending')

    def test_skips_passed_items(self):
        content = """### 1. Setup
expected: Done
result: passed
"""
        items = parse_uat_items(content)
        self.assertEqual(len(items), 0)

    def test_extracts_blocked_with_reason(self):
        content = """### 2. Deploy
expected: App deployed
result: blocked
blocked_by: server not running
"""
        items = parse_uat_items(content)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['category'], 'server_blocked')
        self.assertEqual(items[0]['blocked_by'], 'server not running')

    def test_multiple_items(self):
        content = """### 1. First
expected: A
result: pending

### 2. Second
expected: B
result: skipped
reason: not available

### 3. Third
expected: C
result: passed
"""
        items = parse_uat_items(content)
        self.assertEqual(len(items), 2)


class TestParseVerificationItems(unittest.TestCase):
    def test_human_needed_with_table(self):
        content = """## Human Verification

| # | Test |
|---|------|
| 1 | User can login |
| 2 | Password reset works |
"""
        items = parse_verification_items(content, 'human_needed')
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]['test'], 1)
        self.assertEqual(items[0]['category'], 'human_uat')

    def test_human_needed_with_bullets(self):
        content = """## Human Verification

- Email verification flow works correctly end-to-end
- Short
"""
        items = parse_verification_items(content, 'human_needed')
        self.assertEqual(len(items), 1)  # "Short" is < 10 chars

    def test_gaps_found_returns_empty(self):
        items = parse_verification_items('content', 'gaps_found')
        self.assertEqual(len(items), 0)

    def test_no_section_returns_empty(self):
        items = parse_verification_items('No verification section', 'human_needed')
        self.assertEqual(len(items), 0)


class TestParseCurrentTest(unittest.TestCase):
    def test_parses_inline_expected(self):
        content = """## Current Test

number: 3
name: Environment check
expected: All vars loaded
"""
        result = parse_current_test(content)
        self.assertFalse(result['complete'])
        self.assertEqual(result['number'], 3)
        self.assertEqual(result['name'], 'Environment check')
        self.assertEqual(result['expected'], 'All vars loaded')

    def test_detects_complete(self):
        content = """## Current Test

[testing complete]
"""
        result = parse_current_test(content)
        self.assertTrue(result['complete'])


class TestBuildCheckpoint(unittest.TestCase):
    def test_builds_checkpoint(self):
        result = build_checkpoint({
            'number': 1,
            'name': 'Test login',
            'expected': 'User can login successfully',
        })
        self.assertIn('Test 1: Test login', result)
        self.assertIn('User can login successfully', result)
        self.assertIn('CHECKPOINT', result)
        self.assertIn('pass', result)


if __name__ == '__main__':
    unittest.main()
