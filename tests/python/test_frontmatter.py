"""Tests for lib_py/frontmatter.py — YAML parser and CRUD."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'get-shit-done', 'bin'))

from lib_py.frontmatter import (
    extract_frontmatter, reconstruct_frontmatter, splice_frontmatter,
    parse_must_haves_block, FRONTMATTER_SCHEMAS,
)


class TestExtractFrontmatter(unittest.TestCase):
    def test_simple_key_value(self):
        content = '---\nname: foo\ntype: execute\n---\nbody'
        result = extract_frontmatter(content)
        self.assertEqual(result['name'], 'foo')
        self.assertEqual(result['type'], 'execute')

    def test_strips_quotes(self):
        double = '---\nname: "foo"\n---\n'
        single = "---\nname: 'foo'\n---\n"
        self.assertEqual(extract_frontmatter(double)['name'], 'foo')
        self.assertEqual(extract_frontmatter(single)['name'], 'foo')

    def test_nested_objects(self):
        content = '---\ntechstack:\n  added: prisma\n  patterns: repository\n---\n'
        result = extract_frontmatter(content)
        self.assertEqual(result['techstack'], {'added': 'prisma', 'patterns': 'repository'})

    def test_block_arrays(self):
        content = '---\nitems:\n  - alpha\n  - beta\n  - gamma\n---\n'
        result = extract_frontmatter(content)
        self.assertEqual(result['items'], ['alpha', 'beta', 'gamma'])

    def test_inline_arrays(self):
        content = '---\nkey: [a, b, c]\n---\n'
        result = extract_frontmatter(content)
        self.assertEqual(result['key'], ['a', 'b', 'c'])

    def test_empty_array(self):
        content = '---\nkey: []\n---\n'
        result = extract_frontmatter(content)
        self.assertEqual(result['key'], [])

    def test_no_frontmatter(self):
        content = 'Just plain content.'
        result = extract_frontmatter(content)
        self.assertEqual(result, {})

    def test_empty_frontmatter(self):
        content = '---\n---\nbody'
        result = extract_frontmatter(content)
        self.assertEqual(result, {})


class TestReconstructFrontmatter(unittest.TestCase):
    def test_simple_values(self):
        obj = {'name': 'foo', 'type': 'execute'}
        result = reconstruct_frontmatter(obj)
        self.assertIn('name: foo', result)
        self.assertIn('type: execute', result)

    def test_empty_list(self):
        obj = {'tags': []}
        result = reconstruct_frontmatter(obj)
        self.assertIn('tags: []', result)

    def test_short_list(self):
        obj = {'tags': ['a', 'b']}
        result = reconstruct_frontmatter(obj)
        self.assertIn('tags: [a, b]', result)

    def test_quotes_colons(self):
        obj = {'key': 'value:with:colons'}
        result = reconstruct_frontmatter(obj)
        self.assertIn('"value:with:colons"', result)


class TestSpliceFrontmatter(unittest.TestCase):
    def test_replaces_existing(self):
        content = '---\nold: value\n---\n\n# Body'
        result = splice_frontmatter(content, {'new': 'value'})
        self.assertIn('new: value', result)
        self.assertNotIn('old: value', result)
        self.assertIn('# Body', result)

    def test_adds_when_missing(self):
        content = '# Just body'
        result = splice_frontmatter(content, {'key': 'val'})
        self.assertTrue(result.startswith('---'))
        self.assertIn('key: val', result)
        self.assertIn('# Just body', result)


class TestRoundTrip(unittest.TestCase):
    def test_parse_then_reconstruct(self):
        original = '---\nphase: 03-setup\nplan: 01\ntags: [a, b]\n---\n\n# Body'
        fm = extract_frontmatter(original)
        reconstructed = reconstruct_frontmatter(fm)
        reparsed = extract_frontmatter('---\n%s\n---\n' % reconstructed)
        self.assertEqual(fm['phase'], reparsed['phase'])
        self.assertEqual(fm['plan'], reparsed['plan'])
        self.assertEqual(fm['tags'], reparsed['tags'])


class TestSchemas(unittest.TestCase):
    def test_plan_schema_has_required_fields(self):
        self.assertIn('phase', FRONTMATTER_SCHEMAS['plan']['required'])
        self.assertIn('must_haves', FRONTMATTER_SCHEMAS['plan']['required'])

    def test_summary_schema(self):
        self.assertIn('duration', FRONTMATTER_SCHEMAS['summary']['required'])


if __name__ == '__main__':
    unittest.main()
