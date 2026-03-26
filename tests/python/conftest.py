"""Pytest configuration — ensure test helpers are importable from project root."""
import os
import sys

# Add tests/python/ to sys.path so `from helpers import ...` works from root
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
