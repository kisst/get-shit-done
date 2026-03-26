"""Tests for new core functions — planning paths, milestone filter, etc."""

import os
import sys
import tempfile
import shutil
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'get-shit-done', 'bin'))

from lib_py.core import (
    planning_root, planning_dir, planning_paths,
    strip_shipped_milestones, extract_current_milestone,
    get_milestone_phase_filter, read_subdirectories,
    detect_sub_repos, find_project_root, extract_one_liner_from_body,
    generate_slug_internal,
)


class TestPlanningPaths(unittest.TestCase):
    def test_planning_root(self):
        result = planning_root('/project')
        self.assertTrue(result.endswith('.planning'))

    def test_planning_dir_flat(self):
        result = planning_dir('/project')
        self.assertTrue(result.endswith('.planning'))

    def test_planning_dir_with_workstream(self):
        result = planning_dir('/project', 'my-ws')
        self.assertIn('workstreams', result)
        self.assertIn('my-ws', result)

    def test_planning_paths_returns_dict(self):
        result = planning_paths('/project')
        self.assertIn('state', result)
        self.assertIn('roadmap', result)
        self.assertIn('phases', result)
        self.assertIn('project', result)
        self.assertIn('config', result)


class TestStripShippedMilestones(unittest.TestCase):
    def test_strips_details_blocks(self):
        content = 'Before\n<details>\nShipped stuff\n</details>\nAfter'
        result = strip_shipped_milestones(content)
        self.assertNotIn('Shipped stuff', result)
        self.assertIn('Before', result)
        self.assertIn('After', result)

    def test_no_details_unchanged(self):
        content = 'Just content'
        self.assertEqual(strip_shipped_milestones(content), content)


class TestExtractCurrentMilestone(unittest.TestCase):
    def test_extracts_by_construction_marker(self):
        content = '## Roadmap v1.0: Old\nold stuff\n## Roadmap v2.0: Current 🚧\nnew stuff'
        result = extract_current_milestone(content)
        self.assertIn('new stuff', result)
        self.assertIn('🚧', result)

    def test_returns_full_if_no_marker(self):
        content = '## Phase 1\ncontent'
        result = extract_current_milestone(content)
        self.assertIn('content', result)


class TestGetMilestonePhaseFilter(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.tmp, '.planning'))

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_returns_callable(self):
        with open(os.path.join(self.tmp, '.planning', 'ROADMAP.md'), 'w') as f:
            f.write('### Phase 1: Setup\n### Phase 2: Build\n')
        filt = get_milestone_phase_filter(self.tmp)
        self.assertTrue(callable(filt))
        self.assertTrue(filt('1-setup'))
        self.assertTrue(filt('2-build'))
        self.assertFalse(filt('99-nonexistent'))

    def test_empty_roadmap_accepts_all(self):
        filt = get_milestone_phase_filter(self.tmp)
        self.assertTrue(filt('01-anything'))


class TestReadSubdirectories(unittest.TestCase):
    def test_reads_sorted(self):
        tmp = tempfile.mkdtemp()
        os.makedirs(os.path.join(tmp, 'beta'))
        os.makedirs(os.path.join(tmp, 'alpha'))
        result = read_subdirectories(tmp)
        self.assertEqual(result, ['alpha', 'beta'])
        shutil.rmtree(tmp)

    def test_missing_dir(self):
        result = read_subdirectories('/nonexistent/path')
        self.assertEqual(result, [])


class TestDetectSubRepos(unittest.TestCase):
    def test_finds_git_subdirs(self):
        tmp = tempfile.mkdtemp()
        sub = os.path.join(tmp, 'subrepo')
        os.makedirs(os.path.join(sub, '.git'))
        os.makedirs(os.path.join(tmp, 'normaldir'))
        result = detect_sub_repos(tmp)
        self.assertEqual(result, ['subrepo'])
        shutil.rmtree(tmp)

    def test_ignores_hidden_dirs(self):
        tmp = tempfile.mkdtemp()
        os.makedirs(os.path.join(tmp, '.hidden', '.git'))
        result = detect_sub_repos(tmp)
        self.assertEqual(result, [])
        shutil.rmtree(tmp)


class TestFindProjectRoot(unittest.TestCase):
    def test_finds_local_planning(self):
        tmp = tempfile.mkdtemp()
        os.makedirs(os.path.join(tmp, '.planning'))
        result = find_project_root(tmp)
        self.assertEqual(result, tmp)
        shutil.rmtree(tmp)

    def test_returns_start_if_nothing_found(self):
        tmp = tempfile.mkdtemp()
        result = find_project_root(tmp)
        self.assertEqual(result, tmp)
        shutil.rmtree(tmp)


class TestExtractOneLiner(unittest.TestCase):
    def test_extracts_first_line(self):
        result = extract_one_liner_from_body('First line\nSecond line')
        self.assertEqual(result, 'First line')

    def test_skips_headings(self):
        result = extract_one_liner_from_body('# Heading\nActual content')
        self.assertEqual(result, 'Actual content')

    def test_returns_none_for_empty(self):
        self.assertIsNone(extract_one_liner_from_body(''))
        self.assertIsNone(extract_one_liner_from_body(None))


if __name__ == '__main__':
    unittest.main()
