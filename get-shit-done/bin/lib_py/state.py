"""State — STATE.md operations and progression engine."""

import json
import os
import re
import sys
from datetime import datetime, timezone

from .core import load_config, get_milestone_info, output, error
from .frontmatter import extract_frontmatter, reconstruct_frontmatter


def cmd_state_load(cwd, raw):
    config = load_config(cwd)
    planning_dir = os.path.join(cwd, '.planning')

    state_raw = ''
    try:
        with open(os.path.join(planning_dir, 'STATE.md'), 'r', encoding='utf-8') as f:
            state_raw = f.read()
    except (IOError, OSError):
        pass

    config_exists = os.path.exists(os.path.join(planning_dir, 'config.json'))
    roadmap_exists = os.path.exists(os.path.join(planning_dir, 'ROADMAP.md'))
    state_exists = len(state_raw) > 0

    result = {
        'config': config,
        'state_raw': state_raw,
        'state_exists': state_exists,
        'roadmap_exists': roadmap_exists,
        'config_exists': config_exists,
    }

    if raw:
        c = config
        lines = [
            'model_profile=%s' % c['model_profile'],
            'commit_docs=%s' % str(c['commit_docs']).lower(),
            'branching_strategy=%s' % c['branching_strategy'],
            'phase_branch_template=%s' % c['phase_branch_template'],
            'milestone_branch_template=%s' % c['milestone_branch_template'],
            'parallelization=%s' % str(c['parallelization']).lower(),
            'research=%s' % str(c['research']).lower(),
            'plan_checker=%s' % str(c['plan_checker']).lower(),
            'verifier=%s' % str(c['verifier']).lower(),
            'config_exists=%s' % str(config_exists).lower(),
            'roadmap_exists=%s' % str(roadmap_exists).lower(),
            'state_exists=%s' % str(state_exists).lower(),
        ]
        sys.stdout.write('\n'.join(lines))
        sys.exit(0)

    output(result)


def cmd_state_get(cwd, section, raw):
    state_path = os.path.join(cwd, '.planning', 'STATE.md')
    try:
        with open(state_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except (IOError, OSError):
        error('STATE.md not found')
        return

    if not section:
        output({'content': content}, raw, content)
        return

    field_escaped = re.escape(section)

    field_pattern = re.compile(r'\*\*%s:\*\*\s*(.*)' % field_escaped, re.IGNORECASE)
    field_match = field_pattern.search(content)
    if field_match:
        output({section: field_match.group(1).strip()}, raw, field_match.group(1).strip())
        return

    section_pattern = re.compile(r'##\s*%s\s*\n([\s\S]*?)(?=\n##|$)' % field_escaped, re.IGNORECASE)
    section_match = section_pattern.search(content)
    if section_match:
        output({section: section_match.group(1).strip()}, raw, section_match.group(1).strip())
        return

    output({'error': 'Section or field "%s" not found' % section}, raw, '')


def _read_text_arg_or_file(cwd, value, file_path, label):
    if not file_path:
        return value
    resolved = file_path if os.path.isabs(file_path) else os.path.join(cwd, file_path)
    try:
        with open(resolved, 'r', encoding='utf-8') as f:
            return f.read().rstrip()
    except (IOError, OSError):
        raise ValueError('%s file not found: %s' % (label, file_path))


def state_extract_field(content, field_name):
    """Extract field value from STATE.md content (bold or plain format)."""
    escaped = re.escape(field_name)
    bold = re.compile(r'\*\*%s:\*\*\s*(.+)' % escaped, re.IGNORECASE)
    match = bold.search(content)
    if match:
        return match.group(1).strip()
    plain = re.compile(r'^%s:\s*(.+)' % escaped, re.IGNORECASE | re.MULTILINE)
    match = plain.search(content)
    return match.group(1).strip() if match else None


# Keep internal alias for backward compatibility within this module
_state_extract_field = state_extract_field


def _state_replace_field(content, field_name, new_value):
    escaped = re.escape(field_name)
    pattern = re.compile(r'(\*\*%s:\*\*\s*)(.*)' % escaped, re.IGNORECASE)
    if pattern.search(content):
        return pattern.sub(lambda m: m.group(1) + new_value, content)
    return None


def _strip_frontmatter(content):
    return re.sub(r'^---\n[\s\S]*?\n---\n*', '', content)


def _build_state_frontmatter(body_content, cwd):
    def extract_field(field_name):
        pattern = re.compile(r'\*\*%s:\*\*\s*(.+)' % re.escape(field_name), re.IGNORECASE)
        match = pattern.search(body_content)
        return match.group(1).strip() if match else None

    current_phase = extract_field('Current Phase')
    current_phase_name = extract_field('Current Phase Name')
    current_plan = extract_field('Current Plan')
    total_phases_raw = extract_field('Total Phases')
    total_plans_raw = extract_field('Total Plans in Phase')
    status = extract_field('Status')
    progress_raw = extract_field('Progress')
    last_activity = extract_field('Last Activity')
    stopped_at = extract_field('Stopped At') or extract_field('Stopped at')
    paused_at = extract_field('Paused At')

    milestone = None
    milestone_name = None
    if cwd:
        try:
            info = get_milestone_info(cwd)
            milestone = info['version']
            milestone_name = info['name']
        except (IOError, OSError):
            pass

    total_phases = int(total_phases_raw) if total_phases_raw and total_phases_raw.isdigit() else None
    completed_phases = None
    total_plans = int(total_plans_raw) if total_plans_raw and total_plans_raw.isdigit() else None
    completed_plans = None

    if cwd:
        try:
            phases_dir = os.path.join(cwd, '.planning', 'phases')
            if os.path.exists(phases_dir):
                phase_dirs = [e for e in os.listdir(phases_dir) if os.path.isdir(os.path.join(phases_dir, e))]
                disk_total_plans = 0
                disk_total_summaries = 0
                disk_completed_phases = 0

                for d in phase_dirs:
                    files = os.listdir(os.path.join(phases_dir, d))
                    plans = len([f for f in files if re.search(r'-PLAN\.md$', f, re.IGNORECASE)])
                    summaries = len([f for f in files if re.search(r'-SUMMARY\.md$', f, re.IGNORECASE)])
                    disk_total_plans += plans
                    disk_total_summaries += summaries
                    if plans > 0 and summaries >= plans:
                        disk_completed_phases += 1

                if total_phases is None:
                    total_phases = len(phase_dirs)
                completed_phases = disk_completed_phases
                total_plans = disk_total_plans
                completed_plans = disk_total_summaries
        except (IOError, OSError):
            pass

    progress_percent = None
    if progress_raw:
        pct_match = re.search(r'(\d+)%', progress_raw)
        if pct_match:
            progress_percent = int(pct_match.group(1))

    normalized_status = status or 'unknown'
    status_lower = (status or '').lower()
    if 'paused' in status_lower or 'stopped' in status_lower or paused_at:
        normalized_status = 'paused'
    elif 'executing' in status_lower or 'in progress' in status_lower:
        normalized_status = 'executing'
    elif 'planning' in status_lower or 'ready to plan' in status_lower:
        normalized_status = 'planning'
    elif 'discussing' in status_lower:
        normalized_status = 'discussing'
    elif 'verif' in status_lower:
        normalized_status = 'verifying'
    elif 'complete' in status_lower or 'done' in status_lower:
        normalized_status = 'completed'
    elif 'ready to execute' in status_lower:
        normalized_status = 'executing'

    fm = {'gsd_state_version': '1.0'}
    if milestone:
        fm['milestone'] = milestone
    if milestone_name:
        fm['milestone_name'] = milestone_name
    if current_phase:
        fm['current_phase'] = current_phase
    if current_phase_name:
        fm['current_phase_name'] = current_phase_name
    if current_plan:
        fm['current_plan'] = current_plan
    fm['status'] = normalized_status
    if stopped_at:
        fm['stopped_at'] = stopped_at
    if paused_at:
        fm['paused_at'] = paused_at
    fm['last_updated'] = datetime.now(timezone.utc).isoformat()
    if last_activity:
        fm['last_activity'] = last_activity

    progress = {}
    if total_phases is not None:
        progress['total_phases'] = total_phases
    if completed_phases is not None:
        progress['completed_phases'] = completed_phases
    if total_plans is not None:
        progress['total_plans'] = total_plans
    if completed_plans is not None:
        progress['completed_plans'] = completed_plans
    if progress_percent is not None:
        progress['percent'] = progress_percent
    if progress:
        fm['progress'] = progress

    return fm


def _sync_state_frontmatter(content, cwd):
    body = _strip_frontmatter(content)
    fm = _build_state_frontmatter(body, cwd)
    yaml_str = reconstruct_frontmatter(fm)
    return '---\n%s\n---\n\n%s' % (yaml_str, body)


def write_state_md(state_path, content, cwd):
    synced = _sync_state_frontmatter(content, cwd)
    with open(state_path, 'w', encoding='utf-8') as f:
        f.write(synced)


def cmd_state_patch(cwd, patches, raw):
    state_path = os.path.join(cwd, '.planning', 'STATE.md')
    try:
        with open(state_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except (IOError, OSError):
        error('STATE.md not found')
        return

    results = {'updated': [], 'failed': []}
    for field, value in patches.items():
        escaped = re.escape(field)
        pattern = re.compile(r'(\*\*%s:\*\*\s*)(.*)' % escaped, re.IGNORECASE)
        if pattern.search(content):
            content = pattern.sub(lambda m: m.group(1) + value, content)
            results['updated'].append(field)
        else:
            results['failed'].append(field)

    if results['updated']:
        write_state_md(state_path, content, cwd)
    output(results, raw, 'true' if results['updated'] else 'false')


def cmd_state_update(cwd, field, value):
    if not field or value is None:
        error('field and value required for state update')
    state_path = os.path.join(cwd, '.planning', 'STATE.md')
    try:
        with open(state_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except (IOError, OSError):
        output({'updated': False, 'reason': 'STATE.md not found'})
        return

    result = _state_replace_field(content, field, value)
    if result:
        write_state_md(state_path, result, cwd)
        output({'updated': True})
    else:
        output({'updated': False, 'reason': 'Field "%s" not found in STATE.md' % field})


def cmd_state_advance_plan(cwd, raw):
    state_path = os.path.join(cwd, '.planning', 'STATE.md')
    if not os.path.exists(state_path):
        output({'error': 'STATE.md not found'}, raw)
        return

    with open(state_path, 'r', encoding='utf-8') as f:
        content = f.read()

    current_plan_str = _state_extract_field(content, 'Current Plan')
    total_plans_str = _state_extract_field(content, 'Total Plans in Phase')
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')

    try:
        current_plan = int(current_plan_str)
        total_plans = int(total_plans_str)
    except (TypeError, ValueError):
        output({'error': 'Cannot parse Current Plan or Total Plans in Phase from STATE.md'}, raw)
        return

    if current_plan >= total_plans:
        content = _state_replace_field(content, 'Status', 'Phase complete \u2014 ready for verification') or content
        content = _state_replace_field(content, 'Last Activity', today) or content
        write_state_md(state_path, content, cwd)
        output({'advanced': False, 'reason': 'last_plan', 'current_plan': current_plan, 'total_plans': total_plans, 'status': 'ready_for_verification'}, raw, 'false')
    else:
        new_plan = current_plan + 1
        content = _state_replace_field(content, 'Current Plan', str(new_plan)) or content
        content = _state_replace_field(content, 'Status', 'Ready to execute') or content
        content = _state_replace_field(content, 'Last Activity', today) or content
        write_state_md(state_path, content, cwd)
        output({'advanced': True, 'previous_plan': current_plan, 'current_plan': new_plan, 'total_plans': total_plans}, raw, 'true')


def cmd_state_record_metric(cwd, options, raw):
    state_path = os.path.join(cwd, '.planning', 'STATE.md')
    if not os.path.exists(state_path):
        output({'error': 'STATE.md not found'}, raw)
        return

    with open(state_path, 'r', encoding='utf-8') as f:
        content = f.read()

    phase = options.get('phase')
    plan = options.get('plan')
    duration = options.get('duration')
    tasks = options.get('tasks', '-')
    files = options.get('files', '-')

    if not phase or not plan or not duration:
        output({'error': 'phase, plan, and duration required'}, raw)
        return

    pattern = re.compile(r'(##\s*Performance Metrics[\s\S]*?\n\|[^\n]+\n\|[-|\s]+\n)([\s\S]*?)(?=\n##|\n$|$)', re.IGNORECASE)
    match = pattern.search(content)

    if match:
        table_body = match.group(2).rstrip()
        new_row = '| Phase %s P%s | %s | %s tasks | %s files |' % (phase, plan, duration, tasks, files)
        if not table_body.strip() or 'None yet' in table_body:
            table_body = new_row
        else:
            table_body = table_body + '\n' + new_row

        content = pattern.sub(lambda m: m.group(1) + table_body + '\n', content)
        write_state_md(state_path, content, cwd)
        output({'recorded': True, 'phase': phase, 'plan': plan, 'duration': duration}, raw, 'true')
    else:
        output({'recorded': False, 'reason': 'Performance Metrics section not found in STATE.md'}, raw, 'false')


def cmd_state_update_progress(cwd, raw):
    state_path = os.path.join(cwd, '.planning', 'STATE.md')
    if not os.path.exists(state_path):
        output({'error': 'STATE.md not found'}, raw)
        return

    with open(state_path, 'r', encoding='utf-8') as f:
        content = f.read()

    phases_dir = os.path.join(cwd, '.planning', 'phases')
    total_plans = 0
    total_summaries = 0

    if os.path.exists(phases_dir):
        for d in os.listdir(phases_dir):
            dp = os.path.join(phases_dir, d)
            if not os.path.isdir(dp):
                continue
            files = os.listdir(dp)
            total_plans += len([f for f in files if re.search(r'-PLAN\.md$', f, re.IGNORECASE)])
            total_summaries += len([f for f in files if re.search(r'-SUMMARY\.md$', f, re.IGNORECASE)])

    percent = min(100, round(total_summaries / total_plans * 100)) if total_plans > 0 else 0
    bar_width = 10
    filled = round(percent / 100 * bar_width)
    bar = '\u2588' * filled + '\u2591' * (bar_width - filled)
    progress_str = '[%s] %d%%' % (bar, percent)

    pattern = re.compile(r'(\*\*Progress:\*\*\s*)(.*)', re.IGNORECASE)
    if pattern.search(content):
        content = pattern.sub(lambda m: m.group(1) + progress_str, content)
        write_state_md(state_path, content, cwd)
        output({'updated': True, 'percent': percent, 'completed': total_summaries, 'total': total_plans, 'bar': progress_str}, raw, progress_str)
    else:
        output({'updated': False, 'reason': 'Progress field not found in STATE.md'}, raw, 'false')


def cmd_state_add_decision(cwd, options, raw):
    state_path = os.path.join(cwd, '.planning', 'STATE.md')
    if not os.path.exists(state_path):
        output({'error': 'STATE.md not found'}, raw)
        return

    phase = options.get('phase')
    summary = options.get('summary')
    summary_file = options.get('summary_file')
    rationale = options.get('rationale', '')
    rationale_file = options.get('rationale_file')

    try:
        summary_text = _read_text_arg_or_file(cwd, summary, summary_file, 'summary')
        rationale_text = _read_text_arg_or_file(cwd, rationale, rationale_file, 'rationale')
    except ValueError as e:
        output({'added': False, 'reason': str(e)}, raw, 'false')
        return

    if not summary_text:
        output({'error': 'summary required'}, raw)
        return

    with open(state_path, 'r', encoding='utf-8') as f:
        content = f.read()

    entry = '- [Phase %s]: %s' % (phase or '?', summary_text)
    if rationale_text:
        entry += ' \u2014 %s' % rationale_text

    pattern = re.compile(r'(###?\s*(?:Decisions|Decisions Made|Accumulated.*Decisions)\s*\n)([\s\S]*?)(?=\n###?|\n##[^#]|$)', re.IGNORECASE)
    match = pattern.search(content)

    if match:
        section_body = match.group(2)
        section_body = re.sub(r'None yet\.?\s*\n?', '', section_body, flags=re.IGNORECASE)
        section_body = re.sub(r'No decisions yet\.?\s*\n?', '', section_body, flags=re.IGNORECASE)
        section_body = section_body.rstrip() + '\n' + entry + '\n'
        content = pattern.sub(lambda m: m.group(1) + section_body, content)
        write_state_md(state_path, content, cwd)
        output({'added': True, 'decision': entry}, raw, 'true')
    else:
        output({'added': False, 'reason': 'Decisions section not found in STATE.md'}, raw, 'false')


def cmd_state_add_blocker(cwd, text, raw):
    state_path = os.path.join(cwd, '.planning', 'STATE.md')
    if not os.path.exists(state_path):
        output({'error': 'STATE.md not found'}, raw)
        return

    if isinstance(text, dict):
        blocker_options = text
    else:
        blocker_options = {'text': text}

    try:
        blocker_text = _read_text_arg_or_file(cwd, blocker_options.get('text'), blocker_options.get('text_file'), 'blocker')
    except ValueError as e:
        output({'added': False, 'reason': str(e)}, raw, 'false')
        return

    if not blocker_text:
        output({'error': 'text required'}, raw)
        return

    with open(state_path, 'r', encoding='utf-8') as f:
        content = f.read()
    entry = '- %s' % blocker_text

    pattern = re.compile(r'(###?\s*(?:Blockers|Blockers/Concerns|Concerns)\s*\n)([\s\S]*?)(?=\n###?|\n##[^#]|$)', re.IGNORECASE)
    match = pattern.search(content)

    if match:
        section_body = match.group(2)
        section_body = re.sub(r'None\.?\s*\n?', '', section_body, flags=re.IGNORECASE)
        section_body = re.sub(r'None yet\.?\s*\n?', '', section_body, flags=re.IGNORECASE)
        section_body = section_body.rstrip() + '\n' + entry + '\n'
        content = pattern.sub(lambda m: m.group(1) + section_body, content)
        write_state_md(state_path, content, cwd)
        output({'added': True, 'blocker': blocker_text}, raw, 'true')
    else:
        output({'added': False, 'reason': 'Blockers section not found in STATE.md'}, raw, 'false')


def cmd_state_resolve_blocker(cwd, text, raw):
    state_path = os.path.join(cwd, '.planning', 'STATE.md')
    if not os.path.exists(state_path):
        output({'error': 'STATE.md not found'}, raw)
        return
    if not text:
        output({'error': 'text required'}, raw)
        return

    with open(state_path, 'r', encoding='utf-8') as f:
        content = f.read()

    pattern = re.compile(r'(###?\s*(?:Blockers|Blockers/Concerns|Concerns)\s*\n)([\s\S]*?)(?=\n###?|\n##[^#]|$)', re.IGNORECASE)
    match = pattern.search(content)

    if match:
        section_body = match.group(2)
        lines = section_body.split('\n')
        filtered = [line for line in lines if not (line.startswith('- ') and text.lower() in line.lower())]
        new_body = '\n'.join(filtered)
        if not new_body.strip() or '- ' not in new_body:
            new_body = 'None\n'
        content = pattern.sub(lambda m: m.group(1) + new_body, content)
        write_state_md(state_path, content, cwd)
        output({'resolved': True, 'blocker': text}, raw, 'true')
    else:
        output({'resolved': False, 'reason': 'Blockers section not found in STATE.md'}, raw, 'false')


def cmd_state_record_session(cwd, options, raw):
    state_path = os.path.join(cwd, '.planning', 'STATE.md')
    if not os.path.exists(state_path):
        output({'error': 'STATE.md not found'}, raw)
        return

    with open(state_path, 'r', encoding='utf-8') as f:
        content = f.read()

    now = datetime.now(timezone.utc).isoformat()
    updated = []

    result = _state_replace_field(content, 'Last session', now)
    if result:
        content = result
        updated.append('Last session')
    result = _state_replace_field(content, 'Last Date', now)
    if result:
        content = result
        updated.append('Last Date')

    if options.get('stopped_at'):
        result = _state_replace_field(content, 'Stopped At', options['stopped_at'])
        if not result:
            result = _state_replace_field(content, 'Stopped at', options['stopped_at'])
        if result:
            content = result
            updated.append('Stopped At')

    resume_file = options.get('resume_file', 'None')
    result = _state_replace_field(content, 'Resume File', resume_file)
    if not result:
        result = _state_replace_field(content, 'Resume file', resume_file)
    if result:
        content = result
        updated.append('Resume File')

    if updated:
        write_state_md(state_path, content, cwd)
        output({'recorded': True, 'updated': updated}, raw, 'true')
    else:
        output({'recorded': False, 'reason': 'No session fields found in STATE.md'}, raw, 'false')


def cmd_state_snapshot(cwd, raw):
    state_path = os.path.join(cwd, '.planning', 'STATE.md')
    if not os.path.exists(state_path):
        output({'error': 'STATE.md not found'}, raw)
        return

    with open(state_path, 'r', encoding='utf-8') as f:
        content = f.read()

    def extract_field(field_name):
        pattern = re.compile(r'\*\*%s:\*\*\s*(.+)' % re.escape(field_name), re.IGNORECASE)
        match = pattern.search(content)
        return match.group(1).strip() if match else None

    current_phase = extract_field('Current Phase')
    current_phase_name = extract_field('Current Phase Name')
    total_phases_raw = extract_field('Total Phases')
    current_plan = extract_field('Current Plan')
    total_plans_raw = extract_field('Total Plans in Phase')
    status = extract_field('Status')
    progress_raw = extract_field('Progress')
    last_activity = extract_field('Last Activity')
    last_activity_desc = extract_field('Last Activity Description')
    paused_at = extract_field('Paused At')

    total_phases = int(total_phases_raw) if total_phases_raw and total_phases_raw.isdigit() else None
    total_plans_in_phase = int(total_plans_raw) if total_plans_raw and total_plans_raw.isdigit() else None
    progress_percent = None
    if progress_raw:
        pct_match = re.search(r'(\d+)', progress_raw.replace('%', ' '))
        if pct_match:
            progress_percent = int(pct_match.group(1))

    decisions = []
    dec_match = re.search(r'##\s*Decisions Made[\s\S]*?\n\|[^\n]+\n\|[-|\s]+\n([\s\S]*?)(?=\n##|\n$|$)', content, re.IGNORECASE)
    if dec_match:
        rows = [r for r in dec_match.group(1).strip().split('\n') if '|' in r]
        for row in rows:
            cells = [c.strip() for c in row.split('|') if c.strip()]
            if len(cells) >= 3:
                decisions.append({'phase': cells[0], 'summary': cells[1], 'rationale': cells[2]})

    blockers = []
    blk_match = re.search(r'##\s*Blockers\s*\n([\s\S]*?)(?=\n##|$)', content, re.IGNORECASE)
    if blk_match:
        for item in re.findall(r'^-\s+(.+)$', blk_match.group(1), re.MULTILINE):
            blockers.append(item.strip())

    session = {'last_date': None, 'stopped_at': None, 'resume_file': None}
    sess_match = re.search(r'##\s*Session\s*\n([\s\S]*?)(?=\n##|$)', content, re.IGNORECASE)
    if sess_match:
        s = sess_match.group(1)
        m = re.search(r'\*\*Last Date:\*\*\s*(.+)', s, re.IGNORECASE)
        if m:
            session['last_date'] = m.group(1).strip()
        m = re.search(r'\*\*Stopped At:\*\*\s*(.+)', s, re.IGNORECASE)
        if m:
            session['stopped_at'] = m.group(1).strip()
        m = re.search(r'\*\*Resume File:\*\*\s*(.+)', s, re.IGNORECASE)
        if m:
            session['resume_file'] = m.group(1).strip()

    output({
        'current_phase': current_phase,
        'current_phase_name': current_phase_name,
        'total_phases': total_phases,
        'current_plan': current_plan,
        'total_plans_in_phase': total_plans_in_phase,
        'status': status,
        'progress_percent': progress_percent,
        'last_activity': last_activity,
        'last_activity_desc': last_activity_desc,
        'decisions': decisions,
        'blockers': blockers,
        'paused_at': paused_at,
        'session': session,
    }, raw)


def cmd_state_json(cwd, raw):
    state_path = os.path.join(cwd, '.planning', 'STATE.md')
    if not os.path.exists(state_path):
        output({'error': 'STATE.md not found'}, raw, 'STATE.md not found')
        return

    with open(state_path, 'r', encoding='utf-8') as f:
        content = f.read()

    fm = extract_frontmatter(content)
    if not fm:
        body = _strip_frontmatter(content)
        built = _build_state_frontmatter(body, cwd)
        output(built, raw, json.dumps(built, indent=2))
        return

    output(fm, raw, json.dumps(fm, indent=2))


# ─── New upstream functions (v1.23–v1.29) ────────────────────────────────────

def _update_current_position_fields(content, fields):
    """Update fields within ## Current Position section."""
    section_re = re.compile(
        r'(##\s*Current Position\s*\n)([\s\S]*?)(?=\n##\s|$)', re.IGNORECASE)
    match = section_re.search(content)
    if not match:
        return content

    section = match.group(2)
    for field, value in fields.items():
        escaped = re.escape(field)
        line_re = re.compile(r'(\*\*%s:\*\*\s*)(.*)' % escaped, re.IGNORECASE)
        if line_re.search(section):
            section = line_re.sub(lambda m: m.group(1) + value, section)

    return content[:match.start(2)] + section + content[match.end(2):]


def cmd_state_begin_phase(cwd, phase_number, phase_name, plan_count, raw):
    """Update STATE.md when a new phase begins execution."""
    state_path = os.path.join(cwd, '.planning', 'STATE.md')
    try:
        with open(state_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except (IOError, OSError):
        error('STATE.md not found')
        return

    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    updated = []

    field_updates = {
        'Status': 'Executing phase %s' % phase_number,
        'Last Activity': today,
        'Last Activity Description': 'Began phase %s: %s' % (phase_number, phase_name or ''),
        'Current Phase': str(phase_number),
        'Current Phase Name': phase_name or '',
        'Current Plan': '1',
        'Total Plans in Phase': str(plan_count) if plan_count else '1',
    }

    for field, value in field_updates.items():
        result = _state_replace_field(content, field, value)
        if result:
            content = result
            updated.append(field)

    focus_re = re.compile(r'(\*\*Current focus:\*\*\s*)(.*)', re.IGNORECASE)
    if focus_re.search(content):
        content = focus_re.sub(
            lambda m: m.group(1) + 'Phase %s — %s' % (phase_number, phase_name or ''),
            content)

    content = _update_current_position_fields(content, {
        'Status': 'Executing phase %s' % phase_number,
        'Plan': '1 of %s' % (plan_count or '1'),
    })

    write_state_md(state_path, content, cwd)
    output({'updated': updated, 'phase': str(phase_number),
            'name': phase_name or '', 'plans': plan_count or 1}, raw)


def cmd_signal_waiting(cwd, signal_type, question, options_str, phase, raw):
    """Write WAITING.json signal file when GSD hits a decision point."""
    planning_dir = os.path.join(cwd, '.planning')
    wait_path = os.path.join(planning_dir, 'WAITING.json')

    options_list = [o.strip() for o in options_str.split('|')] if options_str else []

    signal = {
        'status': 'waiting',
        'type': signal_type or 'decision',
        'question': question or '',
        'options': options_list,
        'since': datetime.now(timezone.utc).isoformat(),
        'phase': phase or '',
    }

    os.makedirs(os.path.dirname(wait_path), exist_ok=True)
    with open(wait_path, 'w', encoding='utf-8') as f:
        json.dump(signal, f, indent=2)

    output({'signaled': True, 'path': wait_path}, raw)


def cmd_signal_resume(cwd, raw):
    """Remove WAITING.json signal when user answers and agent resumes."""
    removed = False
    for rel in ('.planning/WAITING.json', '.gsd/WAITING.json'):
        path = os.path.join(cwd, rel)
        if os.path.exists(path):
            os.remove(path)
            removed = True

    output({'resumed': True, 'removed': removed}, raw)
