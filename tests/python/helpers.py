"""Test helpers for GSD Python tests."""

import json
import os
import shutil
import subprocess
import sys
import tempfile

TOOLS_PATH = os.path.join(
    os.path.dirname(__file__), '..', '..', 'get-shit-done', 'bin', 'gsd-tools.py'
)

BIN_DIR = os.path.join(
    os.path.dirname(__file__), '..', '..', 'get-shit-done', 'bin'
)


def run_gsd_tools(args, cwd=None):
    """Run gsd-tools.py with given args. Returns dict with success, output, error."""
    if cwd is None:
        cwd = os.getcwd()
    if isinstance(args, str):
        args = args.split()
    try:
        result = subprocess.run(
            [sys.executable, TOOLS_PATH] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
        )
        return {
            'success': result.returncode == 0,
            'output': result.stdout.strip(),
            'error': result.stderr.strip(),
        }
    except Exception as e:
        return {'success': False, 'output': '', 'error': str(e)}


def create_temp_project():
    """Create a temp directory with .planning/phases/ structure."""
    tmp_dir = tempfile.mkdtemp(prefix='gsd-test-')
    os.makedirs(os.path.join(tmp_dir, '.planning', 'phases'), exist_ok=True)
    return tmp_dir


def create_temp_git_project():
    """Create a temp directory with git repo and initial commit."""
    tmp_dir = tempfile.mkdtemp(prefix='gsd-test-')
    os.makedirs(os.path.join(tmp_dir, '.planning', 'phases'), exist_ok=True)

    subprocess.run(['git', 'init'], cwd=tmp_dir, capture_output=True)
    subprocess.run(['git', 'config', 'user.email', 'test@test.com'], cwd=tmp_dir, capture_output=True)
    subprocess.run(['git', 'config', 'user.name', 'Test'], cwd=tmp_dir, capture_output=True)

    with open(os.path.join(tmp_dir, '.planning', 'PROJECT.md'), 'w') as f:
        f.write('# Project\n\nTest project.\n')

    subprocess.run(['git', 'add', '-A'], cwd=tmp_dir, capture_output=True)
    subprocess.run(['git', 'commit', '-m', 'initial commit'], cwd=tmp_dir, capture_output=True)

    return tmp_dir


def cleanup(tmp_dir):
    """Remove temp directory."""
    shutil.rmtree(tmp_dir, ignore_errors=True)
