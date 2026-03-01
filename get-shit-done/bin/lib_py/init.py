"""
Init - Compound init commands for workflow bootstrapping
"""

import os
import re
import subprocess
from datetime import datetime, timezone

from .core import (
    load_config,
    resolve_model_internal,
    find_phase_internal,
    get_roadmap_phase_internal,
    path_exists_internal,
    generate_slug_internal,
    get_milestone_info,
    normalize_phase_name,
    to_posix_path,
    output,
    error,
)


def _extract_req_ids(roadmap_phase):
    """Extract requirement IDs from a roadmap phase's section text."""
    section = roadmap_phase.get('section') if roadmap_phase else None
    if not section:
        return None
    req_match = re.search(r'^\*\*Requirements\*\*:[^\S\n]*([^\n]*)$', section, re.MULTILINE)
    if not req_match:
        return None
    req_extracted = ', '.join(
        s.strip()
        for s in re.sub(r'[\[\]]', '', req_match.group(1)).split(',')
        if s.strip()
    )
    if req_extracted and req_extracted != 'TBD':
        return req_extracted
    return None


def cmd_init_execute_phase(cwd, phase, raw):
    if not phase:
        error('phase required for init execute-phase')

    config = load_config(cwd)
    phase_info = find_phase_internal(cwd, phase)
    milestone = get_milestone_info(cwd)

    roadmap_phase = get_roadmap_phase_internal(cwd, phase)
    phase_req_ids = _extract_req_ids(roadmap_phase)

    phase_dir = phase_info.get('directory') if phase_info else None
    phase_number = phase_info.get('phase_number') if phase_info else None
    phase_name = phase_info.get('phase_name') if phase_info else None
    phase_slug = phase_info.get('phase_slug') if phase_info else None
    plans = phase_info.get('plans', []) if phase_info else []
    summaries = phase_info.get('summaries', []) if phase_info else []
    incomplete_plans = phase_info.get('incomplete_plans', []) if phase_info else []

    branching_strategy = config.get('branching_strategy')
    phase_branch_template = config.get('phase_branch_template', '')
    milestone_branch_template = config.get('milestone_branch_template', '')

    if branching_strategy == 'phase' and phase_info:
        branch_name = (
            phase_branch_template
            .replace('{phase}', phase_number or '')
            .replace('{slug}', phase_slug or 'phase')
        )
    elif branching_strategy == 'milestone':
        branch_name = (
            milestone_branch_template
            .replace('{milestone}', milestone.get('version', ''))
            .replace('{slug}', generate_slug_internal(milestone.get('name', '')) or 'milestone')
        )
    else:
        branch_name = None

    result = {
        'executor_model': resolve_model_internal(cwd, 'gsd-executor'),
        'verifier_model': resolve_model_internal(cwd, 'gsd-verifier'),

        'commit_docs': config.get('commit_docs'),
        'parallelization': config.get('parallelization'),
        'branching_strategy': branching_strategy,
        'phase_branch_template': phase_branch_template,
        'milestone_branch_template': milestone_branch_template,
        'verifier_enabled': config.get('verifier'),

        'phase_found': bool(phase_info),
        'phase_dir': phase_dir,
        'phase_number': phase_number,
        'phase_name': phase_name,
        'phase_slug': phase_slug,
        'phase_req_ids': phase_req_ids,

        'plans': plans,
        'summaries': summaries,
        'incomplete_plans': incomplete_plans,
        'plan_count': len(plans),
        'incomplete_count': len(incomplete_plans),

        'branch_name': branch_name,

        'milestone_version': milestone.get('version'),
        'milestone_name': milestone.get('name'),
        'milestone_slug': generate_slug_internal(milestone.get('name', '')),

        'state_exists': path_exists_internal(cwd, '.planning/STATE.md'),
        'roadmap_exists': path_exists_internal(cwd, '.planning/ROADMAP.md'),
        'config_exists': path_exists_internal(cwd, '.planning/config.json'),
        'state_path': '.planning/STATE.md',
        'roadmap_path': '.planning/ROADMAP.md',
        'config_path': '.planning/config.json',
    }

    output(result, raw)


def cmd_init_plan_phase(cwd, phase, raw):
    if not phase:
        error('phase required for init plan-phase')

    config = load_config(cwd)
    phase_info = find_phase_internal(cwd, phase)

    roadmap_phase = get_roadmap_phase_internal(cwd, phase)
    phase_req_ids = _extract_req_ids(roadmap_phase)

    phase_dir = phase_info.get('directory') if phase_info else None
    phase_number = phase_info.get('phase_number') if phase_info else None
    phase_name = phase_info.get('phase_name') if phase_info else None
    phase_slug = phase_info.get('phase_slug') if phase_info else None
    plans = phase_info.get('plans', []) if phase_info else []

    padded_phase = phase_number.zfill(2) if phase_number else None

    result = {
        'researcher_model': resolve_model_internal(cwd, 'gsd-phase-researcher'),
        'planner_model': resolve_model_internal(cwd, 'gsd-planner'),
        'checker_model': resolve_model_internal(cwd, 'gsd-plan-checker'),

        'research_enabled': config.get('research'),
        'plan_checker_enabled': config.get('plan_checker'),
        'nyquist_validation_enabled': config.get('nyquist_validation'),
        'commit_docs': config.get('commit_docs'),

        'phase_found': bool(phase_info),
        'phase_dir': phase_dir,
        'phase_number': phase_number,
        'phase_name': phase_name,
        'phase_slug': phase_slug,
        'padded_phase': padded_phase,
        'phase_req_ids': phase_req_ids,

        'has_research': phase_info.get('has_research', False) if phase_info else False,
        'has_context': phase_info.get('has_context', False) if phase_info else False,
        'has_plans': len(plans) > 0,
        'plan_count': len(plans),

        'planning_exists': path_exists_internal(cwd, '.planning'),
        'roadmap_exists': path_exists_internal(cwd, '.planning/ROADMAP.md'),

        'state_path': '.planning/STATE.md',
        'roadmap_path': '.planning/ROADMAP.md',
        'requirements_path': '.planning/REQUIREMENTS.md',
    }

    if phase_dir:
        phase_dir_full = os.path.join(cwd, phase_dir)
        try:
            files = os.listdir(phase_dir_full)
            context_file = next(
                (f for f in files if f.endswith('-CONTEXT.md') or f == 'CONTEXT.md'), None
            )
            if context_file:
                result['context_path'] = to_posix_path(os.path.join(phase_dir, context_file))
            research_file = next(
                (f for f in files if f.endswith('-RESEARCH.md') or f == 'RESEARCH.md'), None
            )
            if research_file:
                result['research_path'] = to_posix_path(os.path.join(phase_dir, research_file))
            verification_file = next(
                (f for f in files if f.endswith('-VERIFICATION.md') or f == 'VERIFICATION.md'), None
            )
            if verification_file:
                result['verification_path'] = to_posix_path(os.path.join(phase_dir, verification_file))
            uat_file = next(
                (f for f in files if f.endswith('-UAT.md') or f == 'UAT.md'), None
            )
            if uat_file:
                result['uat_path'] = to_posix_path(os.path.join(phase_dir, uat_file))
        except OSError:
            pass

    output(result, raw)


def cmd_init_new_project(cwd, raw):
    config = load_config(cwd)

    homedir = os.path.expanduser('~')
    brave_key_file = os.path.join(homedir, '.gsd', 'brave_api_key')
    has_brave_search = bool(os.environ.get('BRAVE_API_KEY') or os.path.exists(brave_key_file))

    has_code = False
    try:
        proc = subprocess.run(
            [
                'find', '.', '-maxdepth', '3',
                '(', '-name', '*.ts', '-o', '-name', '*.js', '-o', '-name', '*.py',
                '-o', '-name', '*.go', '-o', '-name', '*.rs', '-o', '-name', '*.swift',
                '-o', '-name', '*.java', ')',
            ],
            capture_output=True,
            text=True,
            cwd=cwd,
        )
        # Filter out node_modules and .git, limit to 5 results
        lines = [
            l for l in proc.stdout.splitlines()
            if 'node_modules' not in l and '.git' not in l
        ][:5]
        has_code = len(lines) > 0
    except Exception:
        pass

    has_package_file = (
        path_exists_internal(cwd, 'package.json') or
        path_exists_internal(cwd, 'requirements.txt') or
        path_exists_internal(cwd, 'Cargo.toml') or
        path_exists_internal(cwd, 'go.mod') or
        path_exists_internal(cwd, 'Package.swift')
    )

    result = {
        'researcher_model': resolve_model_internal(cwd, 'gsd-project-researcher'),
        'synthesizer_model': resolve_model_internal(cwd, 'gsd-research-synthesizer'),
        'roadmapper_model': resolve_model_internal(cwd, 'gsd-roadmapper'),

        'commit_docs': config.get('commit_docs'),

        'project_exists': path_exists_internal(cwd, '.planning/PROJECT.md'),
        'has_codebase_map': path_exists_internal(cwd, '.planning/codebase'),
        'planning_exists': path_exists_internal(cwd, '.planning'),

        'has_existing_code': has_code,
        'has_package_file': has_package_file,
        'is_brownfield': has_code or has_package_file,
        'needs_codebase_map': (
            (has_code or has_package_file) and
            not path_exists_internal(cwd, '.planning/codebase')
        ),

        'has_git': path_exists_internal(cwd, '.git'),

        'brave_search_available': has_brave_search,

        'project_path': '.planning/PROJECT.md',
    }

    output(result, raw)


def cmd_init_new_milestone(cwd, raw):
    config = load_config(cwd)
    milestone = get_milestone_info(cwd)

    result = {
        'researcher_model': resolve_model_internal(cwd, 'gsd-project-researcher'),
        'synthesizer_model': resolve_model_internal(cwd, 'gsd-research-synthesizer'),
        'roadmapper_model': resolve_model_internal(cwd, 'gsd-roadmapper'),

        'commit_docs': config.get('commit_docs'),
        'research_enabled': config.get('research'),

        'current_milestone': milestone.get('version'),
        'current_milestone_name': milestone.get('name'),

        'project_exists': path_exists_internal(cwd, '.planning/PROJECT.md'),
        'roadmap_exists': path_exists_internal(cwd, '.planning/ROADMAP.md'),
        'state_exists': path_exists_internal(cwd, '.planning/STATE.md'),

        'project_path': '.planning/PROJECT.md',
        'roadmap_path': '.planning/ROADMAP.md',
        'state_path': '.planning/STATE.md',
    }

    output(result, raw)


def cmd_init_quick(cwd, description, raw):
    config = load_config(cwd)
    now = datetime.now(timezone.utc)
    slug = generate_slug_internal(description)[:40] if description else None

    quick_dir = os.path.join(cwd, '.planning', 'quick')
    next_num = 1
    try:
        entries = os.listdir(quick_dir)
        nums = []
        for f in entries:
            if re.match(r'^\d+-', f):
                try:
                    nums.append(int(f.split('-')[0]))
                except ValueError:
                    pass
        if nums:
            next_num = max(nums) + 1
    except OSError:
        pass

    iso_ts = now.isoformat()
    date_str = iso_ts.split('T')[0]

    result = {
        'planner_model': resolve_model_internal(cwd, 'gsd-planner'),
        'executor_model': resolve_model_internal(cwd, 'gsd-executor'),
        'checker_model': resolve_model_internal(cwd, 'gsd-plan-checker'),
        'verifier_model': resolve_model_internal(cwd, 'gsd-verifier'),

        'commit_docs': config.get('commit_docs'),

        'next_num': next_num,
        'slug': slug,
        'description': description if description else None,

        'date': date_str,
        'timestamp': iso_ts,

        'quick_dir': '.planning/quick',
        'task_dir': '.planning/quick/{0}-{1}'.format(next_num, slug) if slug else None,

        'roadmap_exists': path_exists_internal(cwd, '.planning/ROADMAP.md'),
        'planning_exists': path_exists_internal(cwd, '.planning'),
    }

    output(result, raw)


def cmd_init_resume(cwd, raw):
    config = load_config(cwd)

    interrupted_agent_id = None
    try:
        agent_id_path = os.path.join(cwd, '.planning', 'current-agent-id.txt')
        with open(agent_id_path, 'r') as fh:
            interrupted_agent_id = fh.read().strip()
    except OSError:
        pass

    result = {
        'state_exists': path_exists_internal(cwd, '.planning/STATE.md'),
        'roadmap_exists': path_exists_internal(cwd, '.planning/ROADMAP.md'),
        'project_exists': path_exists_internal(cwd, '.planning/PROJECT.md'),
        'planning_exists': path_exists_internal(cwd, '.planning'),

        'state_path': '.planning/STATE.md',
        'roadmap_path': '.planning/ROADMAP.md',
        'project_path': '.planning/PROJECT.md',

        'has_interrupted_agent': bool(interrupted_agent_id),
        'interrupted_agent_id': interrupted_agent_id,

        'commit_docs': config.get('commit_docs'),
    }

    output(result, raw)


def cmd_init_verify_work(cwd, phase, raw):
    if not phase:
        error('phase required for init verify-work')

    config = load_config(cwd)
    phase_info = find_phase_internal(cwd, phase)

    result = {
        'planner_model': resolve_model_internal(cwd, 'gsd-planner'),
        'checker_model': resolve_model_internal(cwd, 'gsd-plan-checker'),

        'commit_docs': config.get('commit_docs'),

        'phase_found': bool(phase_info),
        'phase_dir': phase_info.get('directory') if phase_info else None,
        'phase_number': phase_info.get('phase_number') if phase_info else None,
        'phase_name': phase_info.get('phase_name') if phase_info else None,

        'has_verification': phase_info.get('has_verification', False) if phase_info else False,
    }

    output(result, raw)


def cmd_init_phase_op(cwd, phase, raw):
    config = load_config(cwd)
    phase_info = find_phase_internal(cwd, phase)

    if not phase_info:
        roadmap_phase = get_roadmap_phase_internal(cwd, phase)
        if roadmap_phase and roadmap_phase.get('found'):
            phase_name = roadmap_phase.get('phase_name')
            phase_slug = (
                re.sub(r'^-+|-+$', '', re.sub(r'[^a-z0-9]+', '-', phase_name.lower()))
                if phase_name else None
            )
            phase_info = {
                'found': True,
                'directory': None,
                'phase_number': roadmap_phase.get('phase_number'),
                'phase_name': phase_name,
                'phase_slug': phase_slug,
                'plans': [],
                'summaries': [],
                'incomplete_plans': [],
                'has_research': False,
                'has_context': False,
                'has_verification': False,
            }

    phase_dir = phase_info.get('directory') if phase_info else None
    phase_number = phase_info.get('phase_number') if phase_info else None
    phase_name = phase_info.get('phase_name') if phase_info else None
    phase_slug = phase_info.get('phase_slug') if phase_info else None
    plans = phase_info.get('plans', []) if phase_info else []
    padded_phase = phase_number.zfill(2) if phase_number else None

    result = {
        'commit_docs': config.get('commit_docs'),
        'brave_search': config.get('brave_search'),

        'phase_found': bool(phase_info),
        'phase_dir': phase_dir,
        'phase_number': phase_number,
        'phase_name': phase_name,
        'phase_slug': phase_slug,
        'padded_phase': padded_phase,

        'has_research': phase_info.get('has_research', False) if phase_info else False,
        'has_context': phase_info.get('has_context', False) if phase_info else False,
        'has_plans': len(plans) > 0,
        'has_verification': phase_info.get('has_verification', False) if phase_info else False,
        'plan_count': len(plans),

        'roadmap_exists': path_exists_internal(cwd, '.planning/ROADMAP.md'),
        'planning_exists': path_exists_internal(cwd, '.planning'),

        'state_path': '.planning/STATE.md',
        'roadmap_path': '.planning/ROADMAP.md',
        'requirements_path': '.planning/REQUIREMENTS.md',
    }

    if phase_dir:
        phase_dir_full = os.path.join(cwd, phase_dir)
        try:
            files = os.listdir(phase_dir_full)
            context_file = next(
                (f for f in files if f.endswith('-CONTEXT.md') or f == 'CONTEXT.md'), None
            )
            if context_file:
                result['context_path'] = to_posix_path(os.path.join(phase_dir, context_file))
            research_file = next(
                (f for f in files if f.endswith('-RESEARCH.md') or f == 'RESEARCH.md'), None
            )
            if research_file:
                result['research_path'] = to_posix_path(os.path.join(phase_dir, research_file))
            verification_file = next(
                (f for f in files if f.endswith('-VERIFICATION.md') or f == 'VERIFICATION.md'), None
            )
            if verification_file:
                result['verification_path'] = to_posix_path(os.path.join(phase_dir, verification_file))
            uat_file = next(
                (f for f in files if f.endswith('-UAT.md') or f == 'UAT.md'), None
            )
            if uat_file:
                result['uat_path'] = to_posix_path(os.path.join(phase_dir, uat_file))
        except OSError:
            pass

    output(result, raw)


def cmd_init_todos(cwd, area, raw):
    config = load_config(cwd)
    now = datetime.now(timezone.utc)

    pending_dir = os.path.join(cwd, '.planning', 'todos', 'pending')
    count = 0
    todos = []

    try:
        files = [f for f in os.listdir(pending_dir) if f.endswith('.md')]
        for fname in files:
            try:
                with open(os.path.join(pending_dir, fname), 'r') as fh:
                    content = fh.read()
                created_match = re.search(r'^created:\s*(.+)$', content, re.MULTILINE)
                title_match = re.search(r'^title:\s*(.+)$', content, re.MULTILINE)
                area_match = re.search(r'^area:\s*(.+)$', content, re.MULTILINE)
                todo_area = area_match.group(1).strip() if area_match else 'general'

                if area and todo_area != area:
                    continue

                count += 1
                todos.append({
                    'file': fname,
                    'created': created_match.group(1).strip() if created_match else 'unknown',
                    'title': title_match.group(1).strip() if title_match else 'Untitled',
                    'area': todo_area,
                    'path': '.planning/todos/pending/' + fname,
                })
            except OSError:
                pass
    except OSError:
        pass

    iso_ts = now.isoformat()
    date_str = iso_ts.split('T')[0]

    result = {
        'commit_docs': config.get('commit_docs'),

        'date': date_str,
        'timestamp': iso_ts,

        'todo_count': count,
        'todos': todos,
        'area_filter': area if area else None,

        'pending_dir': '.planning/todos/pending',
        'completed_dir': '.planning/todos/completed',

        'planning_exists': path_exists_internal(cwd, '.planning'),
        'todos_dir_exists': path_exists_internal(cwd, '.planning/todos'),
        'pending_dir_exists': path_exists_internal(cwd, '.planning/todos/pending'),
    }

    output(result, raw)


def cmd_init_milestone_op(cwd, raw):
    config = load_config(cwd)
    milestone = get_milestone_info(cwd)

    phase_count = 0
    completed_phases = 0
    phases_dir = os.path.join(cwd, '.planning', 'phases')
    try:
        entries = os.listdir(phases_dir)
        dirs = [e for e in entries if os.path.isdir(os.path.join(phases_dir, e))]
        phase_count = len(dirs)
        for d in dirs:
            try:
                phase_files = os.listdir(os.path.join(phases_dir, d))
                has_summary = any(
                    f.endswith('-SUMMARY.md') or f == 'SUMMARY.md'
                    for f in phase_files
                )
                if has_summary:
                    completed_phases += 1
            except OSError:
                pass
    except OSError:
        pass

    archive_dir = os.path.join(cwd, '.planning', 'archive')
    archived_milestones = []
    try:
        archived_milestones = [
            e for e in os.listdir(archive_dir)
            if os.path.isdir(os.path.join(archive_dir, e))
        ]
    except OSError:
        pass

    result = {
        'commit_docs': config.get('commit_docs'),

        'milestone_version': milestone.get('version'),
        'milestone_name': milestone.get('name'),
        'milestone_slug': generate_slug_internal(milestone.get('name', '')),

        'phase_count': phase_count,
        'completed_phases': completed_phases,
        'all_phases_complete': phase_count > 0 and phase_count == completed_phases,

        'archived_milestones': archived_milestones,
        'archive_count': len(archived_milestones),

        'project_exists': path_exists_internal(cwd, '.planning/PROJECT.md'),
        'roadmap_exists': path_exists_internal(cwd, '.planning/ROADMAP.md'),
        'state_exists': path_exists_internal(cwd, '.planning/STATE.md'),
        'archive_exists': path_exists_internal(cwd, '.planning/archive'),
        'phases_dir_exists': path_exists_internal(cwd, '.planning/phases'),
    }

    output(result, raw)


def cmd_init_map_codebase(cwd, raw):
    config = load_config(cwd)

    codebase_dir = os.path.join(cwd, '.planning', 'codebase')
    existing_maps = []
    try:
        existing_maps = [f for f in os.listdir(codebase_dir) if f.endswith('.md')]
    except OSError:
        pass

    result = {
        'mapper_model': resolve_model_internal(cwd, 'gsd-codebase-mapper'),

        'commit_docs': config.get('commit_docs'),
        'search_gitignored': config.get('search_gitignored'),
        'parallelization': config.get('parallelization'),

        'codebase_dir': '.planning/codebase',

        'existing_maps': existing_maps,
        'has_maps': len(existing_maps) > 0,

        'planning_exists': path_exists_internal(cwd, '.planning'),
        'codebase_dir_exists': path_exists_internal(cwd, '.planning/codebase'),
    }

    output(result, raw)


def cmd_init_progress(cwd, raw):
    config = load_config(cwd)
    milestone = get_milestone_info(cwd)

    phases_dir = os.path.join(cwd, '.planning', 'phases')
    phases = []
    current_phase = None
    next_phase = None

    try:
        entries = os.listdir(phases_dir)
        dirs = sorted(
            e for e in entries if os.path.isdir(os.path.join(phases_dir, e))
        )

        for d in dirs:
            match = re.match(r'^(\d+(?:\.\d+)*)-?(.*)', d)
            phase_number = match.group(1) if match else d
            phase_name = match.group(2) if (match and match.group(2)) else None

            phase_path = os.path.join(phases_dir, d)
            phase_files = os.listdir(phase_path)

            plans = [
                f for f in phase_files
                if f.endswith('-PLAN.md') or f == 'PLAN.md'
            ]
            summaries = [
                f for f in phase_files
                if f.endswith('-SUMMARY.md') or f == 'SUMMARY.md'
            ]
            has_research = any(
                f.endswith('-RESEARCH.md') or f == 'RESEARCH.md'
                for f in phase_files
            )

            if len(summaries) >= len(plans) and len(plans) > 0:
                status = 'complete'
            elif len(plans) > 0:
                status = 'in_progress'
            elif has_research:
                status = 'researched'
            else:
                status = 'pending'

            phase_entry = {
                'number': phase_number,
                'name': phase_name,
                'directory': '.planning/phases/' + d,
                'status': status,
                'plan_count': len(plans),
                'summary_count': len(summaries),
                'has_research': has_research,
            }

            phases.append(phase_entry)

            if current_phase is None and status in ('in_progress', 'researched'):
                current_phase = phase_entry
            if next_phase is None and status == 'pending':
                next_phase = phase_entry
    except OSError:
        pass

    paused_at = None
    try:
        with open(os.path.join(cwd, '.planning', 'STATE.md'), 'r') as fh:
            state = fh.read()
        pause_match = re.search(r'\*\*Paused At:\*\*\s*(.+)', state)
        if pause_match:
            paused_at = pause_match.group(1).strip()
    except OSError:
        pass

    result = {
        'executor_model': resolve_model_internal(cwd, 'gsd-executor'),
        'planner_model': resolve_model_internal(cwd, 'gsd-planner'),

        'commit_docs': config.get('commit_docs'),

        'milestone_version': milestone.get('version'),
        'milestone_name': milestone.get('name'),

        'phases': phases,
        'phase_count': len(phases),
        'completed_count': sum(1 for p in phases if p['status'] == 'complete'),
        'in_progress_count': sum(1 for p in phases if p['status'] == 'in_progress'),

        'current_phase': current_phase,
        'next_phase': next_phase,
        'paused_at': paused_at,
        'has_work_in_progress': bool(current_phase),

        'project_exists': path_exists_internal(cwd, '.planning/PROJECT.md'),
        'roadmap_exists': path_exists_internal(cwd, '.planning/ROADMAP.md'),
        'state_exists': path_exists_internal(cwd, '.planning/STATE.md'),
        'state_path': '.planning/STATE.md',
        'roadmap_path': '.planning/ROADMAP.md',
        'project_path': '.planning/PROJECT.md',
        'config_path': '.planning/config.json',
    }

    output(result, raw)
