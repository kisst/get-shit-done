#!/usr/bin/env python3
"""Check for GSD updates in background, write result to cache.
Called by SessionStart hook - runs once per session."""

import json
import os
import subprocess
import sys
import time

home_dir = os.path.expanduser('~')
cwd = os.getcwd()
cache_dir = os.path.join(home_dir, '.claude', 'cache')
cache_file = os.path.join(cache_dir, 'gsd-update-check.json')

project_version_file = os.path.join(cwd, '.claude', 'get-shit-done', 'VERSION')
global_version_file = os.path.join(home_dir, '.claude', 'get-shit-done', 'VERSION')

os.makedirs(cache_dir, exist_ok=True)

# Spawn background process to check for updates
bg_script = '''
import json, os, subprocess, time

cache_file = %r
project_version_file = %r
global_version_file = %r

installed = "0.0.0"
try:
    if os.path.exists(project_version_file):
        with open(project_version_file, "r") as f:
            installed = f.read().strip()
    elif os.path.exists(global_version_file):
        with open(global_version_file, "r") as f:
            installed = f.read().strip()
except Exception:
    pass

latest = None
try:
    result = subprocess.run(
        ["npm", "view", "get-shit-done-cc", "version"],
        capture_output=True, text=True, timeout=10,
    )
    if result.returncode == 0:
        latest = result.stdout.strip()
except Exception:
    pass

data = {
    "update_available": bool(latest and installed != latest),
    "installed": installed,
    "latest": latest or "unknown",
    "checked": int(time.time()),
}

with open(cache_file, "w") as f:
    json.dump(data, f)
''' % (cache_file, project_version_file, global_version_file)

child = subprocess.Popen(
    [sys.executable, '-c', bg_script],
    stdin=subprocess.DEVNULL,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
    start_new_session=True,
)
