"""Profile Pipeline — Session scanning, message extraction, and sampling."""

import json
import os
import re
import tempfile
import time

from .core import output, error


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _get_sessions_dir(override_path=None):
    if override_path and os.path.isdir(override_path):
        return override_path
    default = os.path.join(os.path.expanduser('~'), '.claude', 'projects')
    return default if os.path.isdir(default) else None


def _format_bytes(size):
    for unit in ('B', 'KB', 'MB', 'GB'):
        if size < 1024:
            return '%.1f %s' % (size, unit) if unit != 'B' else '%d %s' % (size, unit)
        size /= 1024
    return '%.1f TB' % size


def _is_genuine_user_message(record):
    if record.get('type') != 'user':
        return False
    if record.get('userType') != 'external':
        return False
    if record.get('isMeta') or record.get('isSidechain'):
        return False
    content = record.get('message', {}).get('content', '')
    if not content or not isinstance(content, str):
        return False
    skip_prefixes = ('<local-command', '<command-', '<task-notification', '<local-command-stdout')
    for prefix in skip_prefixes:
        if content.startswith(prefix):
            return False
    return True


def _truncate_content(content, max_len=2000):
    if len(content) <= max_len:
        return content
    return content[:max_len] + '... [truncated]'


def _scan_project_dir(project_dir_path):
    sessions = []
    try:
        for fname in os.listdir(project_dir_path):
            if not fname.endswith('.jsonl'):
                continue
            fpath = os.path.join(project_dir_path, fname)
            try:
                stat = os.stat(fpath)
                sessions.append({
                    'sessionId': fname.replace('.jsonl', ''),
                    'filePath': fpath,
                    'size': stat.st_size,
                    'modified': stat.st_mtime,
                })
            except (IOError, OSError):
                pass
    except (IOError, OSError):
        pass
    sessions.sort(key=lambda s: s['modified'], reverse=True)
    return sessions


def _read_session_index(project_dir_path):
    idx_path = os.path.join(project_dir_path, 'sessions-index.json')
    try:
        with open(idx_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        entries = {}
        for entry in data if isinstance(data, list) else []:
            sid = entry.get('sessionId')
            if sid:
                entries[sid] = entry
        return {'originalPath': None, 'entries': entries}
    except (IOError, OSError, ValueError):
        return {'originalPath': None, 'entries': {}}


def _get_project_name(project_dir_name, index_data, first_record_cwd):
    if index_data and index_data.get('originalPath'):
        return os.path.basename(index_data['originalPath'])
    if first_record_cwd:
        return os.path.basename(first_record_cwd)
    return project_dir_name


def _extract_messages_from_file(file_path, filter_fn, max_messages=300):
    messages = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except (json.JSONDecodeError, ValueError):
                    continue
                if not filter_fn(record):
                    continue
                content = record.get('message', {}).get('content', '')
                messages.append({
                    'sessionId': record.get('sessionId', ''),
                    'projectPath': record.get('cwd', ''),
                    'timestamp': record.get('timestamp', ''),
                    'content': _truncate_content(content),
                })
                if len(messages) >= max_messages:
                    break
    except (IOError, OSError):
        pass
    return messages


# ─── Context Dump Filtering ──────────────────────────────────────────────────

_CONTEXT_DUMP_RE = re.compile(
    r'^\s*(?:\d{4}-\d{2}-\d{2}|DEBUG|INFO|WARN|ERROR|TRACE|\[)', re.IGNORECASE)
_CONTINUATION_RE = re.compile(r'^This session is being continued', re.IGNORECASE)


def _is_log_heavy(content):
    lines = content.split('\n')
    if len(lines) < 5:
        return False
    log_lines = sum(1 for ln in lines if _CONTEXT_DUMP_RE.match(ln))
    return log_lines / len(lines) > 0.5


# ─── Commands ────────────────────────────────────────────────────────────────

def cmd_scan_sessions(override_path, options, raw):
    """List all projects and their sessions."""
    sessions_dir = _get_sessions_dir(override_path)
    if not sessions_dir:
        error('Sessions directory not found')
        return

    projects = []
    try:
        for entry in sorted(os.listdir(sessions_dir)):
            entry_path = os.path.join(sessions_dir, entry)
            if not os.path.isdir(entry_path):
                continue
            sessions = _scan_project_dir(entry_path)
            if not sessions:
                continue
            index_data = _read_session_index(entry_path)
            total_size = sum(s['size'] for s in sessions)
            last_active = max(s['modified'] for s in sessions) if sessions else 0

            projects.append({
                'dir': entry,
                'name': _get_project_name(entry, index_data, None),
                'sessionCount': len(sessions),
                'totalSize': total_size,
                'totalSizeHuman': _format_bytes(total_size),
                'lastActive': time.strftime('%Y-%m-%d', time.gmtime(last_active)),
                'sessions': sessions if options.get('verbose') else [],
            })
    except (IOError, OSError):
        error('Cannot read sessions directory')
        return

    projects.sort(key=lambda p: p.get('lastActive', ''), reverse=True)

    if options.get('json'):
        output({'projects': projects, 'count': len(projects)}, raw)
    else:
        lines = ['%-40s %8s %10s %s' % ('Project', 'Sessions', 'Size', 'Last Active')]
        lines.append('-' * 70)
        for p in projects:
            name = p['name'][:38] if len(p['name']) > 38 else p['name']
            lines.append('%-40s %8d %10s %s' % (
                name, p['sessionCount'], p['totalSizeHuman'], p['lastActive']))
        output({'projects': projects, 'count': len(projects),
                'table': '\n'.join(lines)}, raw)


def cmd_extract_messages(project_arg, options, raw, override_path=None):
    """Extract user messages from a specific project."""
    sessions_dir = _get_sessions_dir(override_path)
    if not sessions_dir:
        error('Sessions directory not found')
        return

    match = None
    try:
        for entry in os.listdir(sessions_dir):
            entry_path = os.path.join(sessions_dir, entry)
            if not os.path.isdir(entry_path):
                continue
            if project_arg.lower() in entry.lower():
                match = entry_path
                break
    except (IOError, OSError):
        error('Cannot read sessions directory')
        return

    if not match:
        error('Project not found matching: %s' % project_arg)
        return

    sessions = _scan_project_dir(match)
    limit = options.get('limit', 10)
    session_id = options.get('sessionId')

    if session_id:
        sessions = [s for s in sessions if s['sessionId'] == session_id]

    all_messages = []
    sessions_processed = 0
    for session in sessions[:limit]:
        msgs = _extract_messages_from_file(
            session['filePath'], _is_genuine_user_message, 300)
        all_messages.extend(msgs)
        sessions_processed += 1

    tmp_dir = os.path.join(tempfile.gettempdir(), 'gsd-profile')
    os.makedirs(tmp_dir, exist_ok=True)
    out_file = os.path.join(tmp_dir, 'messages-%d.jsonl' % int(time.time()))
    with open(out_file, 'w', encoding='utf-8') as f:
        for msg in all_messages:
            f.write(json.dumps(msg) + '\n')

    output({
        'output_file': out_file,
        'sessions_processed': sessions_processed,
        'messages_extracted': len(all_messages),
        'project_dir': match,
    }, raw)


def cmd_profile_sample(override_path, options, raw):
    """Multi-project sampling with recency weighting."""
    sessions_dir = _get_sessions_dir(override_path)
    if not sessions_dir:
        error('Sessions directory not found')
        return

    max_per_project = options.get('maxPerProject', 50)
    max_chars = options.get('maxChars', 500000)
    now = time.time()
    thirty_days = 30 * 86400

    all_messages = []
    breakdown = {}

    try:
        for entry in sorted(os.listdir(sessions_dir)):
            entry_path = os.path.join(sessions_dir, entry)
            if not os.path.isdir(entry_path):
                continue
            sessions = _scan_project_dir(entry_path)
            if not sessions:
                continue

            project_msgs = []
            for session in sessions:
                is_recent = (now - session['modified']) < thirty_days
                per_session_limit = 10 if is_recent else 3
                msgs = _extract_messages_from_file(
                    session['filePath'], _is_genuine_user_message, per_session_limit)
                for msg in msgs:
                    if _CONTINUATION_RE.match(msg.get('content', '')):
                        continue
                    if _is_log_heavy(msg.get('content', '')):
                        continue
                    project_msgs.append(msg)
                    if len(project_msgs) >= max_per_project:
                        break
                if len(project_msgs) >= max_per_project:
                    break

            if project_msgs:
                breakdown[entry] = len(project_msgs)
                all_messages.extend(project_msgs)
    except (IOError, OSError):
        error('Cannot read sessions directory')
        return

    total_chars = 0
    capped = []
    for msg in all_messages:
        total_chars += len(msg.get('content', ''))
        if total_chars > max_chars:
            break
        capped.append(msg)

    tmp_dir = os.path.join(tempfile.gettempdir(), 'gsd-profile')
    os.makedirs(tmp_dir, exist_ok=True)
    out_file = os.path.join(tmp_dir, 'sample-%d.jsonl' % int(time.time()))
    with open(out_file, 'w', encoding='utf-8') as f:
        for msg in capped:
            f.write(json.dumps(msg) + '\n')

    output({
        'output_file': out_file,
        'projects_sampled': len(breakdown),
        'messages_sampled': len(capped),
        'project_breakdown': breakdown,
    }, raw)
