"""UAT Audit — Cross-phase UAT/VERIFICATION scanner."""

import os
import re

from .core import output, error, safe_read_file, to_posix_path
from .frontmatter import extract_frontmatter
from .security import require_safe_path, sanitize_for_display


# ─── Item Categorization ─────────────────────────────────────────────────────

def categorize_item(result, reason=None, blocked_by=None):
    """Classify test items by blocker type and status."""
    if result == 'blocked' or blocked_by:
        if blocked_by:
            bl = blocked_by.lower()
            if 'server' in bl:
                return 'server_blocked'
            if 'device' in bl or 'physical' in bl:
                return 'device_needed'
            if 'build' in bl or 'release' in bl or 'preview' in bl:
                return 'build_needed'
            if 'third' in bl or 'twilio' in bl or 'stripe' in bl:
                return 'third_party'
        return 'blocked'

    if result == 'skipped':
        if reason:
            rl = reason.lower()
            if 'server' in rl or 'not running' in rl or 'not available' in rl:
                return 'server_blocked'
            if 'simulator' in rl or 'physical' in rl or 'device' in rl:
                return 'device_needed'
            if 'build' in rl or 'release' in rl or 'preview' in rl:
                return 'build_needed'
        return 'skipped_unresolved'

    if result == 'pending':
        return 'pending'
    if result == 'human_needed':
        return 'human_uat'
    return 'unknown'


# ─── Parsers ─────────────────────────────────────────────────────────────────

_UAT_BLOCK_RE = re.compile(
    r'###\s*(\d+)\.\s*([^\n]+)\nexpected:\s*([^\n]+)\nresult:\s*(\w+)',
    re.IGNORECASE
)


def parse_uat_items(content):
    """Extract all non-passing test items from UAT markdown content."""
    items = []
    for m in _UAT_BLOCK_RE.finditer(content):
        test_num = int(m.group(1))
        name = m.group(2).strip()
        expected = m.group(3).strip()
        result = m.group(4).strip().lower()

        if result not in ('pending', 'skipped', 'blocked'):
            continue

        rest = content[m.end():]
        next_heading = re.search(r'\n###\s', rest)
        section = rest[:next_heading.start()] if next_heading else rest

        reason_m = re.search(r'reason:\s*(.+)', section)
        blocked_m = re.search(r'blocked_by:\s*(.+)', section)
        reason = reason_m.group(1).strip() if reason_m else None
        blocked_by = blocked_m.group(1).strip() if blocked_m else None

        item = {
            'test': test_num,
            'name': name,
            'expected': expected,
            'result': result,
            'category': categorize_item(result, reason, blocked_by),
        }
        if reason:
            item['reason'] = reason
        if blocked_by:
            item['blocked_by'] = blocked_by
        items.append(item)

    return items


def parse_verification_items(content, status):
    """Extract verification items from VERIFICATION markdown files."""
    if status == 'gaps_found':
        return []
    if status != 'human_needed':
        return []

    section_m = re.search(
        r'##\s*Human Verification.*?\n([\s\S]*?)(?=\n##\s|\n---\s|$)', content, re.IGNORECASE)
    if not section_m:
        return []

    items = []
    for line in section_m.group(1).split('\n'):
        line = line.strip()
        if not line:
            continue

        table_m = re.match(r'\|\s*(\d+)\s*\|\s*([^|]+)', line)
        if table_m:
            items.append({
                'test': int(table_m.group(1)),
                'name': table_m.group(2).strip(),
                'result': 'human_needed',
                'category': 'human_uat',
            })
            continue

        num_m = re.match(r'^(\d+)\.\s+(.+)', line)
        if num_m:
            items.append({
                'test': int(num_m.group(1)),
                'name': num_m.group(2).strip(),
                'result': 'human_needed',
                'category': 'human_uat',
            })
            continue

        bullet_m = re.match(r'^[-*]\s+(.+)', line)
        if bullet_m and len(bullet_m.group(1).strip()) > 10:
            items.append({
                'name': bullet_m.group(1).strip(),
                'result': 'human_needed',
                'category': 'human_uat',
            })

    return items


# ─── Current Test Parsing ────────────────────────────────────────────────────

def parse_current_test(content):
    """Extract current pending test from UAT file's Current Test section."""
    section_m = re.search(
        r'##\s*Current Test\s*(?:\n<!--[\s\S]*?-->)?\n([\s\S]*?)(?=\n##\s|$)',
        content, re.IGNORECASE)
    if not section_m:
        error('No "Current Test" section found')
        return None

    section = section_m.group(1).strip()
    if not section:
        error('Current Test section is empty')
        return None

    if re.search(r'\[testing complete\]', section, re.IGNORECASE):
        return {'complete': True}

    num_m = re.search(r'^number:\s*(\d+)\s*$', section, re.MULTILINE)
    if not num_m:
        error('Missing test number in Current Test section')
        return None

    name_m = re.search(r'^name:\s*(.+)\s*$', section, re.MULTILINE)
    if not name_m:
        error('Missing test name in Current Test section')
        return None

    block_m = re.search(r'^expected:\s*\|\n([\s\S]*?)(?=^\w[\w-]*:\s)', section, re.MULTILINE)
    if block_m:
        lines = block_m.group(1).split('\n')
        expected = '\n'.join(ln[2:] if ln.startswith('  ') else ln for ln in lines).strip()
    else:
        inline_m = re.search(r'^expected:\s*(.+)\s*$', section, re.MULTILINE)
        if not inline_m:
            error('Missing expected outcome in Current Test section')
            return None
        expected = inline_m.group(1).strip()

    return {
        'complete': False,
        'number': int(num_m.group(1)),
        'name': sanitize_for_display(name_m.group(1).strip()),
        'expected': sanitize_for_display(expected),
    }


def build_checkpoint(current_test):
    """Format a test checkpoint as a readable prompt."""
    lines = [
        '\u2554' + '\u2550' * 62 + '\u2557',
        '\u2551  CHECKPOINT: Verification Required' + ' ' * 27 + '\u2551',
        '\u255a' + '\u2550' * 62 + '\u255d',
        '',
        '**Test %d: %s**' % (current_test['number'], current_test['name']),
        '',
        current_test['expected'],
        '',
        '\u2500' * 62,
        'Type `pass` or describe what\'s wrong.',
        '\u2500' * 62,
    ]
    return '\n'.join(lines)


# ─── Commands ────────────────────────────────────────────────────────────────

def _get_milestone_phase_filter(cwd):
    """Return a filter function for phases in the current milestone."""
    roadmap_path = os.path.join(cwd, '.planning', 'ROADMAP.md')
    roadmap = safe_read_file(roadmap_path) or ''

    cleaned = re.sub(r'<details>[\s\S]*?</details>', '', roadmap, flags=re.IGNORECASE)
    phase_nums = set()
    for m in re.finditer(r'###?\s*Phase\s+(\d+[A-Z]?(?:\.\d+)*)', cleaned, re.IGNORECASE):
        phase_nums.add(m.group(1))

    def _filter(dir_name):
        m = re.match(r'^(\d+[A-Z]?(?:\.\d+)*)', dir_name, re.IGNORECASE)
        if not m:
            return False
        if not phase_nums:
            return True
        return m.group(1) in phase_nums

    _filter.phase_count = len(phase_nums)
    return _filter


def cmd_audit_uat(cwd, raw):
    """Scan all phases for UAT and VERIFICATION files."""
    phases_dir = os.path.join(cwd, '.planning', 'phases')
    if not os.path.isdir(phases_dir):
        error('No phases directory found in planning directory')

    is_in_milestone = _get_milestone_phase_filter(cwd)
    results = []

    dirs = sorted(
        (e for e in os.listdir(phases_dir)
         if os.path.isdir(os.path.join(phases_dir, e))),
    )
    dirs = [d for d in dirs if is_in_milestone(d)]

    for d in dirs:
        phase_m = re.match(r'^(\d+[A-Z]?(?:\.\d+)*)', d, re.IGNORECASE)
        phase_num = phase_m.group(1) if phase_m else d
        phase_dir = os.path.join(phases_dir, d)
        files = os.listdir(phase_dir)

        for f in sorted(f for f in files if '-UAT' in f and f.endswith('.md')):
            content = safe_read_file(os.path.join(phase_dir, f)) or ''
            items = parse_uat_items(content)
            results.append({
                'phase': phase_num,
                'phase_dir': d,
                'file': f,
                'file_path': to_posix_path(os.path.join('.planning', 'phases', d, f)),
                'type': 'uat',
                'status': 'unknown',
                'items': items,
            })

        for f in sorted(f for f in files if '-VERIFICATION' in f and f.endswith('.md')):
            content = safe_read_file(os.path.join(phase_dir, f)) or ''
            fm = extract_frontmatter(content)
            status = fm.get('status', '') if fm else ''
            if status not in ('human_needed', 'gaps_found'):
                continue
            items = parse_verification_items(content, status)
            results.append({
                'phase': phase_num,
                'phase_dir': d,
                'file': f,
                'file_path': to_posix_path(os.path.join('.planning', 'phases', d, f)),
                'type': 'verification',
                'status': status,
                'items': items,
            })

    summary = {
        'total_files': len(results),
        'total_items': sum(len(r['items']) for r in results),
        'by_category': {},
        'by_phase': {},
    }
    for r in results:
        for item in r['items']:
            cat = item.get('category', 'unknown')
            summary['by_category'][cat] = summary['by_category'].get(cat, 0) + 1
            summary['by_phase'][r['phase']] = summary['by_phase'].get(r['phase'], 0) + 1

    output({'results': results, 'summary': summary}, raw)


def cmd_render_checkpoint(cwd, options, raw):
    """Render the current pending test from a UAT file."""
    file_path = options.get('file') if options else None
    if not file_path:
        error('--file is required for render-checkpoint')

    resolved = require_safe_path(file_path, cwd, 'UAT file', {'allowAbsolute': True})
    if not os.path.exists(resolved):
        error('UAT file not found: %s' % file_path)

    content = safe_read_file(resolved) or ''
    current = parse_current_test(content)
    if not current:
        return

    if current.get('complete'):
        error('Testing is complete — no pending tests')
        return

    checkpoint = build_checkpoint(current)
    output({
        'file_path': to_posix_path(os.path.relpath(resolved, cwd)),
        'test_number': current['number'],
        'test_name': current['name'],
        'checkpoint': checkpoint,
    }, raw)
