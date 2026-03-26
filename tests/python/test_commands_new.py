"""Tests for new commands — stats, todo-match-phase, commit-to-subrepo."""

import os
import sys
import tempfile
import shutil
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'get-shit-done', 'bin'))


class TestTodoMatchPhase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        planning = os.path.join(self.tmp, '.planning')
        os.makedirs(os.path.join(planning, 'todos', 'pending'))
        os.makedirs(os.path.join(planning, 'phases', '01-setup'))

        with open(os.path.join(planning, 'ROADMAP.md'), 'w') as f:
            f.write('### Phase 1: Setup\n\n**Goal:** Initialize project structure\n')

        with open(os.path.join(planning, 'todos', 'pending', 'todo-1.md'), 'w') as f:
            f.write('title: Fix project initialization\narea: setup\n')
        with open(os.path.join(planning, 'todos', 'pending', 'todo-2.md'), 'w') as f:
            f.write('title: Update documentation\narea: docs\n')

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_matches_relevant_todos(self):
        from lib_py.commands import cmd_todo_match_phase
        with self.assertRaises(SystemExit):
            cmd_todo_match_phase(self.tmp, '1', False)


class TestStats(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        planning = os.path.join(self.tmp, '.planning')
        os.makedirs(os.path.join(planning, 'phases', '01-setup'))
        with open(os.path.join(planning, 'phases', '01-setup', '01-PLAN.md'), 'w') as f:
            f.write('# Plan')
        with open(os.path.join(planning, 'phases', '01-setup', '01-SUMMARY.md'), 'w') as f:
            f.write('# Summary')
        with open(os.path.join(planning, 'STATE.md'), 'w') as f:
            f.write('**Last Activity:** 2026-03-01')
        with open(os.path.join(planning, 'REQUIREMENTS.md'), 'w') as f:
            f.write('- [x] First req\n- [ ] Second req\n')

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_computes_stats(self):
        from lib_py.commands import cmd_stats
        with self.assertRaises(SystemExit):
            cmd_stats(self.tmp, 'json', False)


class TestCommitToSubrepo(unittest.TestCase):
    def test_unmatched_files(self):
        tmp = tempfile.mkdtemp()
        planning = os.path.join(tmp, '.planning')
        os.makedirs(planning)
        with open(os.path.join(planning, 'config.json'), 'w') as f:
            f.write('{}')
        from lib_py.commands import cmd_commit_to_subrepo
        with self.assertRaises(SystemExit):
            cmd_commit_to_subrepo(tmp, 'test commit', ['file.txt'], False)
        shutil.rmtree(tmp)


if __name__ == '__main__':
    unittest.main()
