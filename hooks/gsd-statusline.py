#!/usr/bin/env python3
"""Claude Code Statusline - GSD Edition.
Shows: model | current task | directory | context usage"""

import json
import math
import os
import sys
import tempfile
import time

try:
    data = json.loads(sys.stdin.read())
    model_info = data.get('model') or {}
    model = model_info.get('display_name', 'Claude') if isinstance(model_info, dict) else 'Claude'
    workspace = data.get('workspace') or {}
    directory = workspace.get('current_dir', os.getcwd()) if isinstance(workspace, dict) else os.getcwd()
    session = data.get('session_id', '')
    ctx_window = data.get('context_window') or {}
    remaining = ctx_window.get('remaining_percentage') if isinstance(ctx_window, dict) else None

    ctx = ''
    if remaining is not None:
        rem = round(remaining)
        raw_used = max(0, min(100, 100 - rem))
        used = min(100, round((raw_used / 80) * 100))

        if session:
            try:
                bridge_path = os.path.join(tempfile.gettempdir(), 'claude-ctx-%s.json' % session)
                bridge_data = json.dumps({
                    'session_id': session,
                    'remaining_percentage': remaining,
                    'used_pct': used,
                    'timestamp': int(time.time()),
                })
                with open(bridge_path, 'w') as f:
                    f.write(bridge_data)
            except Exception:
                pass

        filled = used // 10
        bar = '\u2588' * filled + '\u2591' * (10 - filled)

        if used < 63:
            ctx = ' \033[32m%s %d%%\033[0m' % (bar, used)
        elif used < 81:
            ctx = ' \033[33m%s %d%%\033[0m' % (bar, used)
        elif used < 95:
            ctx = ' \033[38;5;208m%s %d%%\033[0m' % (bar, used)
        else:
            ctx = ' \033[5;31m\U0001F480 %s %d%%\033[0m' % (bar, used)

    task = ''
    home_dir = os.path.expanduser('~')
    todos_dir = os.path.join(home_dir, '.claude', 'todos')
    if session and os.path.isdir(todos_dir):
        try:
            files = []
            for f in os.listdir(todos_dir):
                if f.startswith(session) and '-agent-' in f and f.endswith('.json'):
                    fpath = os.path.join(todos_dir, f)
                    files.append((f, os.path.getmtime(fpath)))
            files.sort(key=lambda x: -x[1])

            if files:
                try:
                    with open(os.path.join(todos_dir, files[0][0]), 'r') as fh:
                        todos = json.load(fh)
                    for t in todos:
                        if t.get('status') == 'in_progress':
                            task = t.get('activeForm', '')
                            break
                except Exception:
                    pass
        except Exception:
            pass

    gsd_update = ''
    cache_file = os.path.join(home_dir, '.claude', 'cache', 'gsd-update-check.json')
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r') as f:
                cache = json.load(f)
            if cache.get('update_available'):
                gsd_update = '\033[33m\u2b06 /gsd:update\033[0m \u2502 '
        except Exception:
            pass

    dirname = os.path.basename(directory)
    if task:
        sys.stdout.write('%s\033[2m%s\033[0m \u2502 \033[1m%s\033[0m \u2502 \033[2m%s\033[0m%s' % (gsd_update, model, task, dirname, ctx))
    else:
        sys.stdout.write('%s\033[2m%s\033[0m \u2502 \033[2m%s\033[0m%s' % (gsd_update, model, dirname, ctx))

except Exception:
    pass
