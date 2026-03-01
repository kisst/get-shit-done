"""Roadmap — Roadmap parsing and update operations."""

import os
import re
from datetime import datetime, timezone

from .core import escape_regex, normalize_phase_name, find_phase_internal, output, error


def cmd_roadmap_get_phase(cwd, phase_num, raw):
    roadmap_path = os.path.join(cwd, '.planning', 'ROADMAP.md')

    if not os.path.exists(roadmap_path):
        output({'found': False, 'error': 'ROADMAP.md not found'}, raw, '')
        return

    try:
        with open(roadmap_path, 'r', encoding='utf-8') as f:
            content = f.read()

        escaped_phase = escape_regex(phase_num)

        # Match "## Phase X:", "### Phase X:", or "#### Phase X:" with optional name
        phase_pattern = re.compile(
            r'#{2,4}\s*Phase\s+' + escaped_phase + r':\s*([^\n]+)',
            re.IGNORECASE
        )
        header_match = phase_pattern.search(content)

        if not header_match:
            # Fallback: check if phase exists in summary list but missing detail section
            checklist_pattern = re.compile(
                r'-\s*\[[ x]\]\s*\*\*Phase\s+' + escaped_phase + r':\s*([^*]+)\*\*',
                re.IGNORECASE
            )
            checklist_match = checklist_pattern.search(content)

            if checklist_match:
                output({
                    'found': False,
                    'phase_number': phase_num,
                    'phase_name': checklist_match.group(1).strip(),
                    'error': 'malformed_roadmap',
                    'message': (
                        'Phase %s exists in summary list but missing "### Phase %s:" detail section.'
                        ' ROADMAP.md needs both formats.' % (phase_num, phase_num)
                    ),
                }, raw, '')
                return

            output({'found': False, 'phase_number': phase_num}, raw, '')
            return

        phase_name = header_match.group(1).strip()
        header_index = header_match.start()

        rest_of_content = content[header_index:]
        next_header_match = re.search(r'\n#{2,4}\s+Phase\s+\d', rest_of_content, re.IGNORECASE)
        section_end = header_index + next_header_match.start() if next_header_match else len(content)

        section = content[header_index:section_end].strip()

        goal_match = re.search(r'\*\*Goal:\*\*\s*([^\n]+)', section, re.IGNORECASE)
        goal = goal_match.group(1).strip() if goal_match else None

        criteria_match = re.search(
            r'\*\*Success Criteria\*\*[^\n]*:\s*\n((?:\s*\d+\.\s*[^\n]+\n?)+)',
            section, re.IGNORECASE
        )
        if criteria_match:
            success_criteria = [
                re.sub(r'^\s*\d+\.\s*', '', line).strip()
                for line in criteria_match.group(1).strip().split('\n')
                if line.strip()
            ]
        else:
            success_criteria = []

        output(
            {
                'found': True,
                'phase_number': phase_num,
                'phase_name': phase_name,
                'goal': goal,
                'success_criteria': success_criteria,
                'section': section,
            },
            raw,
            section,
        )
    except (IOError, OSError) as e:
        error('Failed to read ROADMAP.md: ' + str(e))


def cmd_roadmap_analyze(cwd, raw):
    roadmap_path = os.path.join(cwd, '.planning', 'ROADMAP.md')

    if not os.path.exists(roadmap_path):
        output({'error': 'ROADMAP.md not found', 'milestones': [], 'phases': [], 'current_phase': None}, raw)
        return

    with open(roadmap_path, 'r', encoding='utf-8') as f:
        content = f.read()

    phases_dir = os.path.join(cwd, '.planning', 'phases')

    phase_pattern = re.compile(
        r'#{2,4}\s*Phase\s+(\d+[A-Z]?(?:\.\d+)*)\s*:\s*([^\n]+)',
        re.IGNORECASE
    )
    phases = []

    for match in phase_pattern.finditer(content):
        phase_num = match.group(1)
        phase_name = re.sub(r'\(INSERTED\)', '', match.group(2), flags=re.IGNORECASE).strip()

        section_start = match.start()
        rest_of_content = content[section_start:]
        next_header = re.search(r'\n#{2,4}\s+Phase\s+\d', rest_of_content, re.IGNORECASE)
        section_end = section_start + next_header.start() if next_header else len(content)
        section = content[section_start:section_end]

        goal_match = re.search(r'\*\*Goal:\*\*\s*([^\n]+)', section, re.IGNORECASE)
        goal = goal_match.group(1).strip() if goal_match else None

        depends_match = re.search(r'\*\*Depends on:\*\*\s*([^\n]+)', section, re.IGNORECASE)
        depends_on = depends_match.group(1).strip() if depends_match else None

        normalized = normalize_phase_name(phase_num)
        disk_status = 'no_directory'
        plan_count = 0
        summary_count = 0
        has_context = False
        has_research = False

        try:
            entries = os.listdir(phases_dir)
            dirs = [e for e in entries if os.path.isdir(os.path.join(phases_dir, e))]
            dir_match = None
            for d in dirs:
                if d.startswith(normalized + '-') or d == normalized:
                    dir_match = d
                    break

            if dir_match:
                phase_files = os.listdir(os.path.join(phases_dir, dir_match))
                plan_count = len([f for f in phase_files if f.endswith('-PLAN.md') or f == 'PLAN.md'])
                summary_count = len([f for f in phase_files if f.endswith('-SUMMARY.md') or f == 'SUMMARY.md'])
                has_context = any(f.endswith('-CONTEXT.md') or f == 'CONTEXT.md' for f in phase_files)
                has_research = any(f.endswith('-RESEARCH.md') or f == 'RESEARCH.md' for f in phase_files)

                if summary_count >= plan_count and plan_count > 0:
                    disk_status = 'complete'
                elif summary_count > 0:
                    disk_status = 'partial'
                elif plan_count > 0:
                    disk_status = 'planned'
                elif has_research:
                    disk_status = 'researched'
                elif has_context:
                    disk_status = 'discussed'
                else:
                    disk_status = 'empty'
        except (IOError, OSError):
            pass

        checkbox_pattern = re.compile(
            r'-\s*\[(x| )\]\s*.*Phase\s+' + escape_regex(phase_num),
            re.IGNORECASE
        )
        checkbox_match = checkbox_pattern.search(content)
        roadmap_complete = checkbox_match.group(1) == 'x' if checkbox_match else False

        phases.append({
            'number': phase_num,
            'name': phase_name,
            'goal': goal,
            'depends_on': depends_on,
            'plan_count': plan_count,
            'summary_count': summary_count,
            'has_context': has_context,
            'has_research': has_research,
            'disk_status': disk_status,
            'roadmap_complete': roadmap_complete,
        })

    milestones = []
    milestone_pattern = re.compile(r'##\s*(.*v(\d+\.\d+)[^(\n]*)', re.IGNORECASE)
    for m_match in milestone_pattern.finditer(content):
        milestones.append({
            'heading': m_match.group(1).strip(),
            'version': 'v' + m_match.group(2),
        })

    current_phase = next(
        (p for p in phases if p['disk_status'] in ('planned', 'partial')),
        None
    )
    next_phase = next(
        (p for p in phases if p['disk_status'] in ('empty', 'no_directory', 'discussed', 'researched')),
        None
    )

    total_plans = sum(p['plan_count'] for p in phases)
    total_summaries = sum(p['summary_count'] for p in phases)
    completed_phases = len([p for p in phases if p['disk_status'] == 'complete'])

    checklist_pattern = re.compile(r'-\s*\[[ x]\]\s*\*\*Phase\s+(\d+[A-Z]?(?:\.\d+)*)', re.IGNORECASE)
    checklist_phases = set(m.group(1) for m in checklist_pattern.finditer(content))
    detail_phases = set(p['number'] for p in phases)
    missing_details = [p for p in checklist_phases if p not in detail_phases]

    if total_plans > 0:
        progress_percent = min(100, round((total_summaries / total_plans) * 100))
    else:
        progress_percent = 0

    result = {
        'milestones': milestones,
        'phases': phases,
        'phase_count': len(phases),
        'completed_phases': completed_phases,
        'total_plans': total_plans,
        'total_summaries': total_summaries,
        'progress_percent': progress_percent,
        'current_phase': current_phase['number'] if current_phase else None,
        'next_phase': next_phase['number'] if next_phase else None,
        'missing_phase_details': missing_details if missing_details else None,
    }

    output(result, raw)


def cmd_roadmap_update_plan_progress(cwd, phase_num, raw):
    if not phase_num:
        error('phase number required for roadmap update-plan-progress')

    roadmap_path = os.path.join(cwd, '.planning', 'ROADMAP.md')

    phase_info = find_phase_internal(cwd, phase_num)
    if not phase_info:
        error('Phase %s not found' % phase_num)

    plan_count = len(phase_info['plans'])
    summary_count = len(phase_info['summaries'])

    if plan_count == 0:
        output({'updated': False, 'reason': 'No plans found', 'plan_count': 0, 'summary_count': 0}, raw, 'no plans')
        return

    is_complete = summary_count >= plan_count
    if is_complete:
        status = 'Complete'
    elif summary_count > 0:
        status = 'In Progress'
    else:
        status = 'Planned'

    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')

    if not os.path.exists(roadmap_path):
        output(
            {'updated': False, 'reason': 'ROADMAP.md not found', 'plan_count': plan_count, 'summary_count': summary_count},
            raw, 'no roadmap'
        )
        return

    with open(roadmap_path, 'r', encoding='utf-8') as f:
        roadmap_content = f.read()

    phase_escaped = escape_regex(phase_num)

    # Update progress table row: Plans column (summaries/plans) and Status column
    table_pattern = re.compile(
        r'(\|\s*' + phase_escaped + r'\.?\s[^|]*\|)[^|]*(\|)\s*[^|]*(\|)\s*[^|]*(\|)',
        re.IGNORECASE
    )
    date_field = ' %s ' % today if is_complete else '  '
    roadmap_content = table_pattern.sub(
        lambda m: '%s %s/%s %s %s%s%s%s' % (
            m.group(1), summary_count, plan_count,
            m.group(2), status.ljust(11), m.group(3), date_field, m.group(4)
        ),
        roadmap_content
    )

    # Update plan count in phase detail section
    plan_count_pattern = re.compile(
        r'(#{2,4}\s*Phase\s+' + phase_escaped + r'[\s\S]*?\*\*Plans:\*\*\s*)[^\n]+',
        re.IGNORECASE
    )
    if is_complete:
        plan_count_text = '%s/%s plans complete' % (summary_count, plan_count)
    else:
        plan_count_text = '%s/%s plans executed' % (summary_count, plan_count)
    roadmap_content = plan_count_pattern.sub(lambda m: m.group(1) + plan_count_text, roadmap_content)

    # If complete: check checkbox
    if is_complete:
        checkbox_pattern = re.compile(
            r'(-\s*\[)[ ](\]\s*.*Phase\s+' + phase_escaped + r'[:\s][^\n]*)',
            re.IGNORECASE
        )
        roadmap_content = checkbox_pattern.sub(
            lambda m: '%sx%s (completed %s)' % (m.group(1), m.group(2), today),
            roadmap_content
        )

    with open(roadmap_path, 'w', encoding='utf-8') as f:
        f.write(roadmap_content)

    output({
        'updated': True,
        'phase': phase_num,
        'plan_count': plan_count,
        'summary_count': summary_count,
        'status': status,
        'complete': is_complete,
    }, raw, '%s/%s %s' % (summary_count, plan_count, status))
