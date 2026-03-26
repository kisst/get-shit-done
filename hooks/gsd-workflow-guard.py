#!/usr/bin/env python3
"""GSD Workflow Guard — PreToolUse hook.

Detects when Claude attempts file edits outside a GSD workflow context
and injects an advisory warning. This is a SOFT guard — advises, not blocks.

Enable via config: hooks.workflow_guard: true (default: false)
Only triggers on Write/Edit tool calls to non-.planning/ files.
"""

import json
import os
import re
import sys

ALLOWED_PATTERNS = [
    re.compile(r'\.gitignore$'),
    re.compile(r'\.env'),
    re.compile(r'CLAUDE\.md$'),
    re.compile(r'AGENTS\.md$'),
    re.compile(r'GEMINI\.md$'),
    re.compile(r'settings\.json$'),
]


def main():
    try:
        data = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    tool_name = data.get('tool_name', '')
    if tool_name not in ('Write', 'Edit'):
        sys.exit(0)

    tool_input = data.get('tool_input', {})
    if tool_input.get('is_subagent') or data.get('session_type') == 'task':
        sys.exit(0)

    file_path = tool_input.get('file_path', '') or tool_input.get('path', '')
    if '.planning/' in file_path or '.planning\\' in file_path:
        sys.exit(0)

    for pattern in ALLOWED_PATTERNS:
        if pattern.search(file_path):
            sys.exit(0)

    cwd = data.get('cwd', os.getcwd())
    config_path = os.path.join(cwd, '.planning', 'config.json')
    if not os.path.exists(config_path):
        sys.exit(0)

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        if not config.get('hooks', {}).get('workflow_guard'):
            sys.exit(0)
    except (IOError, ValueError):
        sys.exit(0)

    output = {
        'hookSpecificOutput': {
            'hookEventName': 'PreToolUse',
            'additionalContext': (
                '\u26a0\ufe0f WORKFLOW ADVISORY: You\'re editing %s directly without a GSD command. '
                'This edit will not be tracked in STATE.md or produce a SUMMARY.md. '
                'Consider using /gsd:fast for trivial fixes or /gsd:quick for larger changes '
                'to maintain project state tracking. '
                'If this is intentional (e.g., user explicitly asked for a direct edit), proceed normally.'
            ) % os.path.basename(file_path),
        },
    }
    sys.stdout.write(json.dumps(output))
    sys.stdout.flush()


if __name__ == '__main__':
    main()
