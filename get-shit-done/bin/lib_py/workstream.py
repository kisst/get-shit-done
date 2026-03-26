"""Workstream — CRUD operations for workstream namespacing.

Workstreams enable parallel milestones by scoping ROADMAP.md, STATE.md,
REQUIREMENTS.md, and phases/ into .planning/workstreams/{name}/ directories.
"""

import os
import re
import shutil
from datetime import datetime, timezone

from .core import (
    output, error, to_posix_path, generate_slug_internal,
    get_milestone_info, safe_read_file, _phase_sort_key,
)
from .state import state_extract_field


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _planning_root(cwd):
    return os.path.join(cwd, '.planning')


def _validate_ws_name(name):
    if not name or re.search(r'[/\\]', name) or name in ('.', '..'):
        return False
    return True


def _filter_plan_files(files):
    return sorted(f for f in files if f.endswith('-PLAN.md') or f == 'PLAN.md')


def _filter_summary_files(files):
    return sorted(f for f in files if f.endswith('-SUMMARY.md') or f == 'SUMMARY.md')


def _read_subdirectories(base_dir):
    try:
        return sorted(
            e for e in os.listdir(base_dir)
            if os.path.isdir(os.path.join(base_dir, e))
        )
    except (IOError, OSError):
        return []


def _get_active_workstream(cwd):
    ws_file = os.path.join(_planning_root(cwd), 'active-workstream')
    try:
        name = open(ws_file, 'r', encoding='utf-8').read().strip()
        if not re.match(r'^[a-zA-Z0-9_-]+$', name):
            return None
        ws_dir = os.path.join(_planning_root(cwd), 'workstreams', name)
        if os.path.isdir(ws_dir):
            return name
        return None
    except (IOError, OSError):
        return None


def _set_active_workstream(cwd, name):
    ws_file = os.path.join(_planning_root(cwd), 'active-workstream')
    if name is None:
        try:
            os.remove(ws_file)
        except (IOError, OSError):
            pass
    else:
        with open(ws_file, 'w', encoding='utf-8') as f:
            f.write(name)


def _today():
    return datetime.now(timezone.utc).strftime('%Y-%m-%d')


# ─── Migration ───────────────────────────────────────────────────────────────

def migrate_to_workstreams(cwd, workstream_name):
    """Migrate flat .planning/ layout to workstream mode."""
    if not _validate_ws_name(workstream_name):
        raise ValueError('Invalid workstream name for migration')

    base_dir = _planning_root(cwd)
    ws_dir = os.path.join(base_dir, 'workstreams', workstream_name)

    if os.path.exists(os.path.join(base_dir, 'workstreams')):
        raise ValueError('Already in workstream mode — .planning/workstreams/ exists')

    to_move = [
        ('ROADMAP.md', 'file'),
        ('STATE.md', 'file'),
        ('REQUIREMENTS.md', 'file'),
        ('phases', 'dir'),
    ]

    os.makedirs(ws_dir, exist_ok=True)
    moved = []
    try:
        for name, kind in to_move:
            src = os.path.join(base_dir, name)
            dst = os.path.join(ws_dir, name)
            if os.path.exists(src):
                shutil.move(src, dst)
                moved.append(name)
    except Exception:
        for name in reversed(moved):
            src = os.path.join(ws_dir, name)
            dst = os.path.join(base_dir, name)
            if os.path.exists(src):
                shutil.move(src, dst)
        try:
            shutil.rmtree(os.path.join(base_dir, 'workstreams'))
        except (IOError, OSError):
            pass
        raise

    return {'migrated': True, 'workstream': workstream_name, 'files_moved': moved}


# ─── Commands ────────────────────────────────────────────────────────────────

def cmd_workstream_create(cwd, name, options, raw):
    if not name:
        error('Workstream name is required')
    slug = generate_slug_internal(name)
    if not slug:
        error('Invalid workstream name')

    base_dir = _planning_root(cwd)
    if not os.path.isdir(base_dir):
        error('.planning/ directory not found — run init first')

    ws_dir = os.path.join(base_dir, 'workstreams', slug)
    if os.path.isdir(ws_dir) and os.path.exists(os.path.join(ws_dir, 'STATE.md')):
        output({'created': False, 'error': 'already_exists',
                'workstream': slug,
                'path': to_posix_path(os.path.relpath(ws_dir, cwd))}, raw)
        return

    ws_root = os.path.join(base_dir, 'workstreams')
    has_existing_work = (
        os.path.exists(os.path.join(base_dir, 'ROADMAP.md')) or
        os.path.exists(os.path.join(base_dir, 'STATE.md')) or
        os.path.isdir(os.path.join(base_dir, 'phases'))
    )

    migration = None
    if not os.path.isdir(ws_root):
        if has_existing_work and options.get('migrate') is not False:
            migrate_name = options.get('migrateName')
            if not migrate_name:
                info = get_milestone_info(cwd)
                migrate_name = info.get('name', 'default')
            migrate_slug = generate_slug_internal(migrate_name) or 'default'
            try:
                migration = migrate_to_workstreams(cwd, migrate_slug)
            except Exception as exc:
                output({'created': False, 'error': 'migration_failed',
                        'workstream': slug, 'message': str(exc),
                        'path': to_posix_path(os.path.relpath(ws_dir, cwd))}, raw)
                return
        else:
            os.makedirs(ws_root, exist_ok=True)

    os.makedirs(os.path.join(ws_dir, 'phases'), exist_ok=True)

    state_content = '\n'.join([
        '---',
        'workstream: %s' % slug,
        'created: %s' % _today(),
        '---',
        '',
        '**Status:** Not started',
        '**Current Phase:** None',
        '**Last Activity:** %s' % _today(),
        '**Last Activity Description:** Workstream created',
        '**Phases Complete:** 0',
        '**Current Plan:** N/A',
        '**Stopped At:** N/A',
        '**Resume File:** None',
        '',
    ])
    with open(os.path.join(ws_dir, 'STATE.md'), 'w', encoding='utf-8') as f:
        f.write(state_content)

    _set_active_workstream(cwd, slug)

    rel_path = to_posix_path(os.path.relpath(ws_dir, cwd))
    output({
        'created': True,
        'workstream': slug,
        'path': rel_path,
        'state_path': rel_path + '/STATE.md',
        'phases_path': rel_path + '/phases',
        'migration': migration,
        'active': True,
    }, raw)


def cmd_workstream_list(cwd, raw):
    ws_root = os.path.join(_planning_root(cwd), 'workstreams')
    if not os.path.isdir(ws_root):
        output({'mode': 'flat', 'workstreams': [], 'count': 0,
                'message': 'No workstreams directory — operating in flat mode'}, raw)
        return

    workstreams = []
    for ws_name in _read_subdirectories(ws_root):
        ws_dir = os.path.join(ws_root, ws_name)
        phases_dir = os.path.join(ws_dir, 'phases')
        phase_dirs = _read_subdirectories(phases_dir) if os.path.isdir(phases_dir) else []

        total = len(phase_dirs)
        completed = 0
        for pd in phase_dirs:
            files = os.listdir(os.path.join(phases_dir, pd))
            plans = _filter_plan_files(files)
            summaries = _filter_summary_files(files)
            if plans and len(summaries) >= len(plans):
                completed += 1

        state_content = safe_read_file(os.path.join(ws_dir, 'STATE.md')) or ''
        status = state_extract_field(state_content, 'Status') or 'unknown'
        current_phase = state_extract_field(state_content, 'Current Phase')

        workstreams.append({
            'name': ws_name,
            'path': to_posix_path(os.path.relpath(ws_dir, cwd)),
            'has_roadmap': os.path.exists(os.path.join(ws_dir, 'ROADMAP.md')),
            'has_state': os.path.exists(os.path.join(ws_dir, 'STATE.md')),
            'status': status,
            'current_phase': current_phase,
            'phase_count': total,
            'completed_phases': completed,
        })

    output({'mode': 'workstream', 'workstreams': workstreams,
            'count': len(workstreams)}, raw)


def cmd_workstream_status(cwd, name, raw):
    if not _validate_ws_name(name):
        error('Invalid workstream name')

    ws_dir = os.path.join(_planning_root(cwd), 'workstreams', name)
    if not os.path.isdir(ws_dir):
        output({'found': False, 'workstream': name}, raw)
        return

    files_info = {
        'roadmap': os.path.exists(os.path.join(ws_dir, 'ROADMAP.md')),
        'state': os.path.exists(os.path.join(ws_dir, 'STATE.md')),
        'requirements': os.path.exists(os.path.join(ws_dir, 'REQUIREMENTS.md')),
    }

    phases_dir = os.path.join(ws_dir, 'phases')
    phases = []
    completed = 0
    for pd in (_read_subdirectories(phases_dir) if os.path.isdir(phases_dir) else []):
        pd_path = os.path.join(phases_dir, pd)
        files = os.listdir(pd_path)
        plans = _filter_plan_files(files)
        summaries = _filter_summary_files(files)
        if plans and len(summaries) >= len(plans):
            status = 'complete'
            completed += 1
        elif plans:
            status = 'in_progress'
        else:
            status = 'pending'
        phases.append({
            'directory': pd,
            'status': status,
            'plan_count': len(plans),
            'summary_count': len(summaries),
        })

    state_content = safe_read_file(os.path.join(ws_dir, 'STATE.md')) or ''
    output({
        'found': True,
        'workstream': name,
        'path': to_posix_path(os.path.relpath(ws_dir, cwd)),
        'files': files_info,
        'phases': phases,
        'phase_count': len(phases),
        'completed_phases': completed,
        'status': state_extract_field(state_content, 'Status') or 'unknown',
        'current_phase': state_extract_field(state_content, 'Current Phase'),
        'last_activity': state_extract_field(state_content, 'Last Activity'),
    }, raw)


def cmd_workstream_complete(cwd, name, options, raw):
    if not _validate_ws_name(name):
        error('Invalid workstream name')

    ws_dir = os.path.join(_planning_root(cwd), 'workstreams', name)
    if not os.path.isdir(ws_dir):
        output({'completed': False, 'error': 'not_found', 'workstream': name}, raw)
        return

    active = _get_active_workstream(cwd)
    if active == name:
        _set_active_workstream(cwd, None)

    base_dir = _planning_root(cwd)
    archive_base = 'ws-%s-%s' % (name, _today())
    archive_path = os.path.join(base_dir, 'milestones', archive_base)
    suffix = 0
    while os.path.exists(archive_path):
        suffix += 1
        archive_path = os.path.join(base_dir, 'milestones', '%s-%d' % (archive_base, suffix))

    os.makedirs(archive_path, exist_ok=True)
    moved = []
    try:
        for entry in os.listdir(ws_dir):
            src = os.path.join(ws_dir, entry)
            dst = os.path.join(archive_path, entry)
            shutil.move(src, dst)
            moved.append(entry)
    except Exception as exc:
        for entry in reversed(moved):
            src = os.path.join(archive_path, entry)
            dst = os.path.join(ws_dir, entry)
            if os.path.exists(src):
                shutil.move(src, dst)
        if active == name:
            _set_active_workstream(cwd, name)
        output({'completed': False, 'error': 'archive_failed',
                'workstream': name, 'message': str(exc)}, raw)
        return

    try:
        os.rmdir(ws_dir)
    except (IOError, OSError):
        pass

    ws_root = os.path.join(base_dir, 'workstreams')
    remaining = _read_subdirectories(ws_root)
    reverted = False
    if len(remaining) == 0:
        try:
            os.rmdir(ws_root)
            reverted = True
        except (IOError, OSError):
            pass

    output({
        'completed': True,
        'workstream': name,
        'archived_to': to_posix_path(os.path.relpath(archive_path, cwd)),
        'remaining_workstreams': len(remaining),
        'reverted_to_flat': reverted,
    }, raw)


def cmd_workstream_set(cwd, name, raw):
    if not name:
        _set_active_workstream(cwd, None)
        output({'active': None, 'set': True, 'cleared': True}, raw)
        return

    if not re.match(r'^[a-zA-Z0-9_-]+$', name):
        output({'active': None, 'error': 'invalid_name',
                'message': 'Name must be alphanumeric with hyphens/underscores',
                'workstream': name}, raw)
        return

    ws_dir = os.path.join(_planning_root(cwd), 'workstreams', name)
    if not os.path.isdir(ws_dir):
        output({'active': None, 'error': 'not_found',
                'message': 'Workstream not found',
                'workstream': name}, raw)
        return

    _set_active_workstream(cwd, name)
    output({'active': name, 'set': True}, raw, name)


def cmd_workstream_get(cwd, raw):
    active = _get_active_workstream(cwd)
    ws_root = os.path.join(_planning_root(cwd), 'workstreams')
    mode = 'workstream' if os.path.isdir(ws_root) else 'flat'
    output({'active': active, 'mode': mode}, raw)


def cmd_workstream_progress(cwd, raw):
    ws_root = os.path.join(_planning_root(cwd), 'workstreams')
    if not os.path.isdir(ws_root):
        output({'mode': 'flat', 'active': None, 'workstreams': [], 'count': 0,
                'message': 'No workstreams directory — operating in flat mode'}, raw)
        return

    active = _get_active_workstream(cwd)
    workstreams = []

    for ws_name in _read_subdirectories(ws_root):
        ws_dir = os.path.join(ws_root, ws_name)
        phases_dir = os.path.join(ws_dir, 'phases')
        phase_dirs = _read_subdirectories(phases_dir) if os.path.isdir(phases_dir) else []

        total_plans = 0
        completed_plans = 0
        completed_phases = 0
        for pd in phase_dirs:
            files = os.listdir(os.path.join(phases_dir, pd))
            plans = _filter_plan_files(files)
            summaries = _filter_summary_files(files)
            total_plans += len(plans)
            completed_plans += len(summaries)
            if plans and len(summaries) >= len(plans):
                completed_phases += 1

        roadmap_content = safe_read_file(os.path.join(ws_dir, 'ROADMAP.md')) or ''
        roadmap_phases = len(re.findall(r'###?\s*Phase\s+\d', roadmap_content, re.IGNORECASE))
        if roadmap_phases == 0:
            roadmap_phases = len(phase_dirs)

        state_content = safe_read_file(os.path.join(ws_dir, 'STATE.md')) or ''
        status = state_extract_field(state_content, 'Status') or 'unknown'
        current_phase = state_extract_field(state_content, 'Current Phase')

        progress = int((completed_phases / roadmap_phases * 100)) if roadmap_phases > 0 else 0

        workstreams.append({
            'name': ws_name,
            'active': ws_name == active,
            'status': status,
            'current_phase': current_phase,
            'phases': '%d/%d' % (completed_phases, roadmap_phases),
            'plans': '%d/%d' % (completed_plans, total_plans),
            'progress_percent': progress,
        })

    output({'mode': 'workstream', 'active': active,
            'workstreams': workstreams, 'count': len(workstreams)}, raw)


def get_other_active_workstreams(cwd, exclude_ws):
    """Return non-completed workstreams except the specified one."""
    ws_root = os.path.join(_planning_root(cwd), 'workstreams')
    if not os.path.isdir(ws_root):
        return []

    results = []
    for ws_name in _read_subdirectories(ws_root):
        if ws_name == exclude_ws:
            continue
        ws_dir = os.path.join(ws_root, ws_name)
        state_content = safe_read_file(os.path.join(ws_dir, 'STATE.md')) or ''
        status = state_extract_field(state_content, 'Status') or 'unknown'
        if re.search(r'milestone complete|archived', status, re.IGNORECASE):
            continue

        phases_dir = os.path.join(ws_dir, 'phases')
        phase_dirs = _read_subdirectories(phases_dir) if os.path.isdir(phases_dir) else []
        completed = 0
        for pd in phase_dirs:
            files = os.listdir(os.path.join(phases_dir, pd))
            plans = _filter_plan_files(files)
            summaries = _filter_summary_files(files)
            if plans and len(summaries) >= len(plans):
                completed += 1

        results.append({
            'name': ws_name,
            'status': status,
            'current_phase': state_extract_field(state_content, 'Current Phase'),
            'phases': '%d/%d' % (completed, len(phase_dirs)),
        })

    return results
