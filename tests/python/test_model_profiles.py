"""Tests for model_profiles module — profile resolution, mapping."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'get-shit-done', 'bin'))

from lib_py.model_profiles import (
    VALID_PROFILES, get_agent_to_model_map_for_profile,
    format_agent_to_model_map_as_table, EXTENDED_PROFILES,
)


class TestValidProfiles(unittest.TestCase):
    def test_three_profiles(self):
        self.assertEqual(VALID_PROFILES, ['quality', 'balanced', 'budget'])


class TestGetAgentToModelMap(unittest.TestCase):
    def test_quality_profile(self):
        mapping = get_agent_to_model_map_for_profile('quality')
        self.assertIn('gsd-planner', mapping)
        self.assertEqual(mapping['gsd-planner'], 'opus')

    def test_budget_profile(self):
        mapping = get_agent_to_model_map_for_profile('budget')
        self.assertIn('gsd-planner', mapping)
        self.assertEqual(mapping['gsd-planner'], 'sonnet')

    def test_balanced_profile(self):
        mapping = get_agent_to_model_map_for_profile('balanced')
        self.assertIn('gsd-codebase-mapper', mapping)
        self.assertEqual(mapping['gsd-codebase-mapper'], 'haiku')

    def test_invalid_defaults_to_balanced(self):
        mapping = get_agent_to_model_map_for_profile('nonexistent')
        balanced = get_agent_to_model_map_for_profile('balanced')
        self.assertEqual(mapping, balanced)

    def test_includes_extended_agents(self):
        mapping = get_agent_to_model_map_for_profile('quality')
        for agent in EXTENDED_PROFILES:
            self.assertIn(agent, mapping)


class TestFormatTable(unittest.TestCase):
    def test_formats_table(self):
        mapping = {'gsd-planner': 'opus', 'gsd-verifier': 'sonnet'}
        table = format_agent_to_model_map_as_table(mapping)
        self.assertIn('gsd-planner', table)
        self.assertIn('opus', table)
        self.assertIn('Agent', table)

    def test_empty_mapping(self):
        result = format_agent_to_model_map_as_table({})
        self.assertEqual(result, '')


if __name__ == '__main__':
    unittest.main()
