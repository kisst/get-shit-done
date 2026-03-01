#!/usr/bin/env python3
"""Context Monitor - PostToolUse hook.

Reads context metrics from the statusline bridge file and injects
warnings when context usage is high.
"""

import json
import os
import sys
import tempfile
import time

WARNING_THRESHOLD = 35
CRITICAL_THRESHOLD = 25
STALE_SECONDS = 60
DEBOUNCE_CALLS = 5

try:
    data = json.loads(sys.stdin.read())
    session_id = data.get('session_id')

    if not session_id:
        sys.exit(0)

    tmp_dir = tempfile.gettempdir()
    metrics_path = os.path.join(tmp_dir, 'claude-ctx-%s.json' % session_id)

    if not os.path.exists(metrics_path):
        sys.exit(0)

    with open(metrics_path, 'r') as f:
        metrics = json.load(f)

    now = int(time.time())
    if metrics.get('timestamp') and (now - metrics['timestamp']) > STALE_SECONDS:
        sys.exit(0)

    remaining = metrics.get('remaining_percentage', 100)
    used_pct = metrics.get('used_pct', 0)

    if remaining > WARNING_THRESHOLD:
        sys.exit(0)

    warn_path = os.path.join(tmp_dir, 'claude-ctx-%s-warned.json' % session_id)
    warn_data = {'callsSinceWarn': 0, 'lastLevel': None}
    first_warn = True

    if os.path.exists(warn_path):
        try:
            with open(warn_path, 'r') as f:
                warn_data = json.load(f)
            first_warn = False
        except Exception:
            pass

    warn_data['callsSinceWarn'] = (warn_data.get('callsSinceWarn') or 0) + 1

    is_critical = remaining <= CRITICAL_THRESHOLD
    current_level = 'critical' if is_critical else 'warning'

    severity_escalated = current_level == 'critical' and warn_data.get('lastLevel') == 'warning'
    if not first_warn and warn_data['callsSinceWarn'] < DEBOUNCE_CALLS and not severity_escalated:
        with open(warn_path, 'w') as f:
            json.dump(warn_data, f)
        sys.exit(0)

    warn_data['callsSinceWarn'] = 0
    warn_data['lastLevel'] = current_level
    with open(warn_path, 'w') as f:
        json.dump(warn_data, f)

    if is_critical:
        message = (
            'CONTEXT MONITOR CRITICAL: Usage at %s%%. Remaining: %s%%. '
            'STOP new work immediately. Save state NOW and inform the user that context is nearly exhausted. '
            'If using GSD, run /gsd:pause-work to save execution state.'
        ) % (used_pct, remaining)
    else:
        message = (
            'CONTEXT MONITOR WARNING: Usage at %s%%. Remaining: %s%%. '
            'Begin wrapping up current task. Do not start new complex work. '
            'If using GSD, consider /gsd:pause-work to save state.'
        ) % (used_pct, remaining)

    output = {
        'hookSpecificOutput': {
            'hookEventName': 'PostToolUse',
            'additionalContext': message,
        }
    }
    sys.stdout.write(json.dumps(output))

except Exception:
    sys.exit(0)
