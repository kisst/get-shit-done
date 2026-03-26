"""Verify — Verification suite, consistency, and health validation."""

import json
import os
import re
import shutil
from datetime import datetime, timezone

from .core import (
    safe_read_file,
    normalize_phase_name,
    exec_git,
    find_phase_internal,
    get_milestone_info,
    output,
    error,
)
from .frontmatter import extract_frontmatter, parse_must_haves_block
from .state import write_state_md


def cmd_verify_summary(cwd, summary_path, check_file_count, raw):
    if not summary_path:
        error('summary-path required')

    full_path = os.path.join(cwd, summary_path)
    check_count = check_file_count or 2

    if not os.path.exists(full_path):
        result = {
            'passed': False,
            'checks': {
                'summary_exists': False,
                'files_created': {'checked': 0, 'found': 0, 'missing': []},
                'commits_exist': False,
                'self_check': 'not_found',
            },
            'errors': ['SUMMARY.md not found'],
        }
        output(result, raw, 'failed')
        return

    with open(full_path, 'r', encoding='utf-8') as f:
        content = f.read()
    errors = []

    # Spot-check files mentioned in summary
    mentioned_files = set()
    patterns = [
        re.compile(r'`([^`]+\.[a-zA-Z]+)`', re.MULTILINE),
        re.compile(r'(?:Created|Modified|Added|Updated|Edited):\s*`?([^\s`]+\.[a-zA-Z]+)`?', re.IGNORECASE),
    ]
    for pattern in patterns:
        for m in pattern.finditer(content):
            file_path = m.group(1)
            if file_path and not file_path.startswith('http') and '/' in file_path:
                mentioned_files.add(file_path)

    files_to_check = list(mentioned_files)[:check_count]
    missing = []
    for f in files_to_check:
        if not os.path.exists(os.path.join(cwd, f)):
            missing.append(f)

    # Check commits exist
    commit_hash_pattern = re.compile(r'\b[0-9a-f]{7,40}\b')
    hashes = commit_hash_pattern.findall(content)
    commits_exist = False
    if hashes:
        for h in hashes[:3]:
            result = exec_git(cwd, ['cat-file', '-t', h])
            if result['exitCode'] == 0 and result['stdout'] == 'commit':
                commits_exist = True
                break

    # Self-check section
    self_check = 'not_found'
    self_check_pattern = re.compile(r'##\s*(?:Self[- ]?Check|Verification|Quality Check)', re.IGNORECASE)
    if self_check_pattern.search(content):
        pass_pattern = re.compile(r'(?:all\s+)?(?:pass|✓|✅|complete|succeeded)', re.IGNORECASE)
        fail_pattern = re.compile(r'(?:fail|✗|❌|incomplete|blocked)', re.IGNORECASE)
        start = self_check_pattern.search(content).start()
        check_section = content[start:]
        if fail_pattern.search(check_section):
            self_check = 'failed'
        elif pass_pattern.search(check_section):
            self_check = 'passed'

    if missing:
        errors.append('Missing files: ' + ', '.join(missing))
    if not commits_exist and hashes:
        errors.append('Referenced commit hashes not found in git history')
    if self_check == 'failed':
        errors.append('Self-check section indicates failure')

    checks = {
        'summary_exists': True,
        'files_created': {
            'checked': len(files_to_check),
            'found': len(files_to_check) - len(missing),
            'missing': missing,
        },
        'commits_exist': commits_exist,
        'self_check': self_check,
    }

    passed = len(missing) == 0 and self_check != 'failed'
    result = {'passed': passed, 'checks': checks, 'errors': errors}
    output(result, raw, 'passed' if passed else 'failed')


def cmd_verify_plan_structure(cwd, file_path, raw):
    if not file_path:
        error('file path required')
    full_path = file_path if os.path.isabs(file_path) else os.path.join(cwd, file_path)
    content = safe_read_file(full_path)
    if not content:
        output({'error': 'File not found', 'path': file_path}, raw)
        return

    fm = extract_frontmatter(content)
    errors = []
    warnings = []

    required = ['phase', 'plan', 'type', 'wave', 'depends_on', 'files_modified', 'autonomous', 'must_haves']
    for field in required:
        if field not in fm:
            errors.append('Missing required frontmatter field: %s' % field)

    task_pattern = re.compile(r'<task[^>]*>([\s\S]*?)</task>')
    tasks = []
    for task_match in task_pattern.finditer(content):
        task_content = task_match.group(1)
        name_match = re.search(r'<name>([\s\S]*?)</name>', task_content)
        task_name = name_match.group(1).strip() if name_match else 'unnamed'
        has_files = bool(re.search(r'<files>', task_content))
        has_action = bool(re.search(r'<action>', task_content))
        has_verify = bool(re.search(r'<verify>', task_content))
        has_done = bool(re.search(r'<done>', task_content))

        if not name_match:
            errors.append('Task missing <name> element')
        if not has_action:
            errors.append("Task '%s' missing <action>" % task_name)
        if not has_verify:
            warnings.append("Task '%s' missing <verify>" % task_name)
        if not has_done:
            warnings.append("Task '%s' missing <done>" % task_name)
        if not has_files:
            warnings.append("Task '%s' missing <files>" % task_name)

        tasks.append({
            'name': task_name,
            'hasFiles': has_files,
            'hasAction': has_action,
            'hasVerify': has_verify,
            'hasDone': has_done,
        })

    if not tasks:
        warnings.append('No <task> elements found')

    wave = fm.get('wave')
    depends_on = fm.get('depends_on')
    if wave:
        try:
            wave_int = int(wave)
        except (ValueError, TypeError):
            wave_int = 0
        if wave_int > 1 and (not depends_on or (isinstance(depends_on, list) and len(depends_on) == 0)):
            warnings.append('Wave > 1 but depends_on is empty')

    has_checkpoints = bool(re.search(r'<task\s+type=["\']?checkpoint', content))
    autonomous = fm.get('autonomous')
    if has_checkpoints and autonomous != 'false' and autonomous is not False:
        errors.append('Has checkpoint tasks but autonomous is not false')

    output({
        'valid': len(errors) == 0,
        'errors': errors,
        'warnings': warnings,
        'task_count': len(tasks),
        'tasks': tasks,
        'frontmatter_fields': list(fm.keys()),
    }, raw, 'valid' if len(errors) == 0 else 'invalid')


def cmd_verify_phase_completeness(cwd, phase, raw):
    if not phase:
        error('phase required')
    phase_info = find_phase_internal(cwd, phase)
    if not phase_info or not phase_info.get('found'):
        output({'error': 'Phase not found', 'phase': phase}, raw)
        return

    errors = []
    warnings = []
    phase_dir = os.path.join(cwd, phase_info['directory'])

    try:
        files = os.listdir(phase_dir)
    except (IOError, OSError):
        output({'error': 'Cannot read phase directory'}, raw)
        return

    plans = [f for f in files if re.search(r'-PLAN\.md$', f, re.IGNORECASE)]
    summaries = [f for f in files if re.search(r'-SUMMARY\.md$', f, re.IGNORECASE)]

    plan_ids = set(re.sub(r'-PLAN\.md$', '', p, flags=re.IGNORECASE) for p in plans)
    summary_ids = set(re.sub(r'-SUMMARY\.md$', '', s, flags=re.IGNORECASE) for s in summaries)

    incomplete_plans = [pid for pid in plan_ids if pid not in summary_ids]
    if incomplete_plans:
        errors.append('Plans without summaries: %s' % ', '.join(incomplete_plans))

    orphan_summaries = [sid for sid in summary_ids if sid not in plan_ids]
    if orphan_summaries:
        warnings.append('Summaries without plans: %s' % ', '.join(orphan_summaries))

    output({
        'complete': len(errors) == 0,
        'phase': phase_info['phase_number'],
        'plan_count': len(plans),
        'summary_count': len(summaries),
        'incomplete_plans': incomplete_plans,
        'orphan_summaries': orphan_summaries,
        'errors': errors,
        'warnings': warnings,
    }, raw, 'complete' if len(errors) == 0 else 'incomplete')


def cmd_verify_references(cwd, file_path, raw):
    if not file_path:
        error('file path required')
    full_path = file_path if os.path.isabs(file_path) else os.path.join(cwd, file_path)
    content = safe_read_file(full_path)
    if not content:
        output({'error': 'File not found', 'path': file_path}, raw)
        return

    found = []
    missing = []

    at_refs = re.findall(r'@([^\s\n,)]+/[^\s\n,)]+)', content)
    for clean_ref in at_refs:
        if clean_ref.startswith('~/'):
            resolved = os.path.join(os.environ.get('HOME', ''), clean_ref[2:])
        else:
            resolved = os.path.join(cwd, clean_ref)
        if os.path.exists(resolved):
            found.append(clean_ref)
        else:
            missing.append(clean_ref)

    backtick_matches = re.findall(r'`([^`]+/[^`]+\.[a-zA-Z]{1,10})`', content)
    for clean_ref in backtick_matches:
        if clean_ref.startswith('http') or '${' in clean_ref or '{{' in clean_ref:
            continue
        if clean_ref in found or clean_ref in missing:
            continue
        resolved = os.path.join(cwd, clean_ref)
        if os.path.exists(resolved):
            found.append(clean_ref)
        else:
            missing.append(clean_ref)

    output({
        'valid': len(missing) == 0,
        'found': len(found),
        'missing': missing,
        'total': len(found) + len(missing),
    }, raw, 'valid' if len(missing) == 0 else 'invalid')


def cmd_verify_commits(cwd, hashes, raw):
    if not hashes or len(hashes) == 0:
        error('At least one commit hash required')

    valid = []
    invalid = []
    for h in hashes:
        result = exec_git(cwd, ['cat-file', '-t', h])
        if result['exitCode'] == 0 and result['stdout'].strip() == 'commit':
            valid.append(h)
        else:
            invalid.append(h)

    output({
        'all_valid': len(invalid) == 0,
        'valid': valid,
        'invalid': invalid,
        'total': len(hashes),
    }, raw, 'valid' if len(invalid) == 0 else 'invalid')


def cmd_verify_artifacts(cwd, plan_file_path, raw):
    if not plan_file_path:
        error('plan file path required')
    full_path = plan_file_path if os.path.isabs(plan_file_path) else os.path.join(cwd, plan_file_path)
    content = safe_read_file(full_path)
    if not content:
        output({'error': 'File not found', 'path': plan_file_path}, raw)
        return

    artifacts = parse_must_haves_block(content, 'artifacts')
    if not artifacts:
        output({'error': 'No must_haves.artifacts found in frontmatter', 'path': plan_file_path}, raw)
        return

    results = []
    for artifact in artifacts:
        if isinstance(artifact, str):
            continue
        art_path = artifact.get('path')
        if not art_path:
            continue

        art_full_path = os.path.join(cwd, art_path)
        exists = os.path.exists(art_full_path)
        check = {'path': art_path, 'exists': exists, 'issues': [], 'passed': False}

        if exists:
            file_content = safe_read_file(art_full_path) or ''
            line_count = len(file_content.split('\n'))

            min_lines = artifact.get('min_lines')
            if min_lines and line_count < min_lines:
                check['issues'].append('Only %d lines, need %d' % (line_count, min_lines))

            contains = artifact.get('contains')
            if contains and contains not in file_content:
                check['issues'].append('Missing pattern: %s' % contains)

            exports = artifact.get('exports')
            if exports:
                export_list = exports if isinstance(exports, list) else [exports]
                for exp in export_list:
                    if exp not in file_content:
                        check['issues'].append('Missing export: %s' % exp)

            check['passed'] = len(check['issues']) == 0
        else:
            check['issues'].append('File not found')

        results.append(check)

    passed = len([r for r in results if r['passed']])
    output({
        'all_passed': passed == len(results),
        'passed': passed,
        'total': len(results),
        'artifacts': results,
    }, raw, 'valid' if passed == len(results) else 'invalid')


def cmd_verify_key_links(cwd, plan_file_path, raw):
    if not plan_file_path:
        error('plan file path required')
    full_path = plan_file_path if os.path.isabs(plan_file_path) else os.path.join(cwd, plan_file_path)
    content = safe_read_file(full_path)
    if not content:
        output({'error': 'File not found', 'path': plan_file_path}, raw)
        return

    key_links = parse_must_haves_block(content, 'key_links')
    if not key_links:
        output({'error': 'No must_haves.key_links found in frontmatter', 'path': plan_file_path}, raw)
        return

    results = []
    for link in key_links:
        if isinstance(link, str):
            continue
        check = {
            'from': link.get('from'),
            'to': link.get('to'),
            'via': link.get('via', ''),
            'verified': False,
            'detail': '',
        }

        source_content = safe_read_file(os.path.join(cwd, link.get('from') or ''))
        if not source_content:
            check['detail'] = 'Source file not found'
        elif link.get('pattern'):
            try:
                regex = re.compile(link['pattern'])
                if regex.search(source_content):
                    check['verified'] = True
                    check['detail'] = 'Pattern found in source'
                else:
                    target_content = safe_read_file(os.path.join(cwd, link.get('to') or ''))
                    if target_content and regex.search(target_content):
                        check['verified'] = True
                        check['detail'] = 'Pattern found in target'
                    else:
                        check['detail'] = 'Pattern "%s" not found in source or target' % link['pattern']
            except re.error:
                check['detail'] = 'Invalid regex pattern: %s' % link['pattern']
        else:
            to_val = link.get('to') or ''
            if to_val in source_content:
                check['verified'] = True
                check['detail'] = 'Target referenced in source'
            else:
                check['detail'] = 'Target not referenced in source'

        results.append(check)

    verified = len([r for r in results if r['verified']])
    output({
        'all_verified': verified == len(results),
        'verified': verified,
        'total': len(results),
        'links': results,
    }, raw, 'valid' if verified == len(results) else 'invalid')


def cmd_validate_consistency(cwd, raw):
    roadmap_path = os.path.join(cwd, '.planning', 'ROADMAP.md')
    phases_dir = os.path.join(cwd, '.planning', 'phases')
    errors = []
    warnings = []

    if not os.path.exists(roadmap_path):
        errors.append('ROADMAP.md not found')
        output({'passed': False, 'errors': errors, 'warnings': warnings}, raw, 'failed')
        return

    with open(roadmap_path, 'r', encoding='utf-8') as f:
        roadmap_content = f.read()

    roadmap_phases = set()
    phase_pattern = re.compile(r'#{2,4}\s*Phase\s+(\d+[A-Z]?(?:\.\d+)*)\s*:', re.IGNORECASE)
    for m in phase_pattern.finditer(roadmap_content):
        roadmap_phases.add(m.group(1))

    disk_phases = set()
    try:
        entries = os.listdir(phases_dir)
        dirs = [e for e in entries if os.path.isdir(os.path.join(phases_dir, e))]
        for d in dirs:
            dm = re.match(r'^(\d+[A-Z]?(?:\.\d+)*)', d, re.IGNORECASE)
            if dm:
                disk_phases.add(dm.group(1))
    except (IOError, OSError):
        pass

    for p in roadmap_phases:
        if p not in disk_phases and normalize_phase_name(p) not in disk_phases:
            warnings.append('Phase %s in ROADMAP.md but no directory on disk' % p)

    for p in disk_phases:
        unpadded = str(int(p)) if p.isdigit() else p
        if p not in roadmap_phases and unpadded not in roadmap_phases:
            warnings.append('Phase %s exists on disk but not in ROADMAP.md' % p)

    integer_phases = sorted(
        int(p) for p in disk_phases if not '.' in p and p.isdigit()
    )
    for i in range(1, len(integer_phases)):
        if integer_phases[i] != integer_phases[i - 1] + 1:
            warnings.append('Gap in phase numbering: %d -> %d' % (integer_phases[i - 1], integer_phases[i]))

    # Check plan numbering within phases
    try:
        entries = os.listdir(phases_dir)
        dirs = sorted(e for e in entries if os.path.isdir(os.path.join(phases_dir, e)))

        for d in dirs:
            phase_files = os.listdir(os.path.join(phases_dir, d))
            plans = sorted(f for f in phase_files if f.endswith('-PLAN.md'))
            summaries = [f for f in phase_files if f.endswith('-SUMMARY.md')]

            plan_nums = []
            for p in plans:
                pm = re.search(r'-(\d{2})-PLAN\.md$', p)
                if pm:
                    plan_nums.append(int(pm.group(1)))

            for i in range(1, len(plan_nums)):
                if plan_nums[i] != plan_nums[i - 1] + 1:
                    warnings.append(
                        'Gap in plan numbering in %s: plan %d -> %d' % (d, plan_nums[i - 1], plan_nums[i])
                    )

            plan_ids = set(p.replace('-PLAN.md', '') for p in plans)
            summary_ids = set(s.replace('-SUMMARY.md', '') for s in summaries)

            for sid in summary_ids:
                if sid not in plan_ids:
                    warnings.append(
                        'Summary %s-SUMMARY.md in %s has no matching PLAN.md' % (sid, d)
                    )
    except (IOError, OSError):
        pass

    # Check frontmatter in plans
    try:
        entries = os.listdir(phases_dir)
        dirs = [e for e in entries if os.path.isdir(os.path.join(phases_dir, e))]

        for d in dirs:
            phase_files = os.listdir(os.path.join(phases_dir, d))
            plans = [f for f in phase_files if f.endswith('-PLAN.md')]

            for plan in plans:
                plan_content = safe_read_file(os.path.join(phases_dir, d, plan))
                if plan_content:
                    fm = extract_frontmatter(plan_content)
                    if not fm.get('wave'):
                        warnings.append("%s/%s: missing 'wave' in frontmatter" % (d, plan))
    except (IOError, OSError):
        pass

    passed = len(errors) == 0
    output(
        {'passed': passed, 'errors': errors, 'warnings': warnings, 'warning_count': len(warnings)},
        raw,
        'passed' if passed else 'failed',
    )


def cmd_validate_health(cwd, options, raw):
    planning_dir = os.path.join(cwd, '.planning')
    project_path = os.path.join(planning_dir, 'PROJECT.md')
    roadmap_path = os.path.join(planning_dir, 'ROADMAP.md')
    state_path = os.path.join(planning_dir, 'STATE.md')
    config_path = os.path.join(planning_dir, 'config.json')
    phases_dir = os.path.join(planning_dir, 'phases')

    errors = []
    warnings = []
    info = []
    repairs = []

    def add_issue(severity, code, message, fix, repairable=False):
        issue = {'code': code, 'message': message, 'fix': fix, 'repairable': repairable}
        if severity == 'error':
            errors.append(issue)
        elif severity == 'warning':
            warnings.append(issue)
        else:
            info.append(issue)

    # Check 1: .planning/ exists
    if not os.path.exists(planning_dir):
        add_issue('error', 'E001', '.planning/ directory not found', 'Run /gsd:new-project to initialize')
        output({'status': 'broken', 'errors': errors, 'warnings': warnings, 'info': info, 'repairable_count': 0}, raw)
        return

    # Check 2: PROJECT.md exists and has required sections
    if not os.path.exists(project_path):
        add_issue('error', 'E002', 'PROJECT.md not found', 'Run /gsd:new-project to create')
    else:
        with open(project_path, 'r', encoding='utf-8') as f:
            proj_content = f.read()
        for section in ['## What This Is', '## Core Value', '## Requirements']:
            if section not in proj_content:
                add_issue('warning', 'W001', 'PROJECT.md missing section: %s' % section, 'Add section manually')

    # Check 3: ROADMAP.md exists
    if not os.path.exists(roadmap_path):
        add_issue('error', 'E003', 'ROADMAP.md not found', 'Run /gsd:new-milestone to create roadmap')

    # Check 4: STATE.md exists and references valid phases
    if not os.path.exists(state_path):
        add_issue('error', 'E004', 'STATE.md not found', 'Run /gsd:health --repair to regenerate', True)
        repairs.append('regenerateState')
    else:
        with open(state_path, 'r', encoding='utf-8') as f:
            state_content = f.read()
        phase_refs = re.findall(r'[Pp]hase\s+(\d+(?:\.\d+)*)', state_content)
        disk_phases = set()
        try:
            entries = os.listdir(phases_dir)
            for e in entries:
                if os.path.isdir(os.path.join(phases_dir, e)):
                    m = re.match(r'^(\d+(?:\.\d+)*)', e)
                    if m:
                        disk_phases.add(m.group(1))
        except (IOError, OSError):
            pass
        for ref in phase_refs:
            try:
                normalized_ref = str(int(ref)).zfill(2)
                unpadded_ref = str(int(ref))
            except (ValueError, TypeError):
                normalized_ref = ref
                unpadded_ref = ref
            if ref not in disk_phases and normalized_ref not in disk_phases and unpadded_ref not in disk_phases:
                if disk_phases:
                    add_issue(
                        'warning', 'W002',
                        'STATE.md references phase %s, but only phases %s exist' % (ref, ', '.join(sorted(disk_phases))),
                        'Run /gsd:health --repair to regenerate STATE.md',
                        True,
                    )
                    if 'regenerateState' not in repairs:
                        repairs.append('regenerateState')

    # Check 5: config.json valid JSON + valid schema
    if not os.path.exists(config_path):
        add_issue('warning', 'W003', 'config.json not found', 'Run /gsd:health --repair to create with defaults', True)
        repairs.append('createConfig')
    else:
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                raw_config = f.read()
            parsed = json.loads(raw_config)
            valid_profiles = ['quality', 'balanced', 'budget']
            model_profile = parsed.get('model_profile')
            if model_profile and model_profile not in valid_profiles:
                add_issue(
                    'warning', 'W004',
                    'config.json: invalid model_profile "%s"' % model_profile,
                    'Valid values: %s' % ', '.join(valid_profiles),
                )
        except (ValueError, IOError, OSError) as err:
            add_issue(
                'error', 'E005',
                'config.json: JSON parse error - %s' % str(err),
                'Run /gsd:health --repair to reset to defaults',
                True,
            )
            repairs.append('resetConfig')

    # Check 6: Phase directory naming (NN-name format)
    try:
        entries = os.listdir(phases_dir)
        for name in entries:
            if os.path.isdir(os.path.join(phases_dir, name)):
                if not re.match(r'^\d{2}(?:\.\d+)*-[\w-]+$', name):
                    add_issue(
                        'warning', 'W005',
                        'Phase directory "%s" doesn\'t follow NN-name format' % name,
                        'Rename to match pattern (e.g., 01-setup)',
                    )
    except (IOError, OSError):
        pass

    # Check 7: Orphaned plans (PLAN without SUMMARY)
    try:
        entries = os.listdir(phases_dir)
        for name in entries:
            if not os.path.isdir(os.path.join(phases_dir, name)):
                continue
            phase_files = os.listdir(os.path.join(phases_dir, name))
            plans = [f for f in phase_files if f.endswith('-PLAN.md') or f == 'PLAN.md']
            summaries = [f for f in phase_files if f.endswith('-SUMMARY.md') or f == 'SUMMARY.md']
            summary_bases = set(
                s.replace('-SUMMARY.md', '').replace('SUMMARY.md', '') for s in summaries
            )
            for plan in plans:
                plan_base = plan.replace('-PLAN.md', '').replace('PLAN.md', '')
                if plan_base not in summary_bases:
                    add_issue('info', 'I001', '%s/%s has no SUMMARY.md' % (name, plan), 'May be in progress')
    except (IOError, OSError):
        pass

    # Check 8: Inline consistency checks against ROADMAP
    if os.path.exists(roadmap_path):
        with open(roadmap_path, 'r', encoding='utf-8') as f:
            roadmap_content = f.read()
        roadmap_phases = set()
        phase_pattern = re.compile(r'#{2,4}\s*Phase\s+(\d+[A-Z]?(?:\.\d+)*)\s*:', re.IGNORECASE)
        for m in phase_pattern.finditer(roadmap_content):
            roadmap_phases.add(m.group(1))

        disk_phases2 = set()
        try:
            entries = os.listdir(phases_dir)
            for e in entries:
                if os.path.isdir(os.path.join(phases_dir, e)):
                    dm = re.match(r'^(\d+[A-Z]?(?:\.\d+)*)', e, re.IGNORECASE)
                    if dm:
                        disk_phases2.add(dm.group(1))
        except (IOError, OSError):
            pass

        for p in roadmap_phases:
            try:
                padded = str(int(p)).zfill(2)
            except (ValueError, TypeError):
                padded = p
            if p not in disk_phases2 and padded not in disk_phases2:
                add_issue(
                    'warning', 'W006',
                    'Phase %s in ROADMAP.md but no directory on disk' % p,
                    'Create phase directory or remove from roadmap',
                )

        for p in disk_phases2:
            try:
                unpadded = str(int(p))
            except (ValueError, TypeError):
                unpadded = p
            if p not in roadmap_phases and unpadded not in roadmap_phases:
                add_issue(
                    'warning', 'W007',
                    'Phase %s exists on disk but not in ROADMAP.md' % p,
                    'Add to roadmap or remove directory',
                )

    # Perform repairs if requested
    repair_actions = []
    if options.get('repair') and repairs:
        for repair in repairs:
            try:
                if repair in ('createConfig', 'resetConfig'):
                    defaults = {
                        'model_profile': 'balanced',
                        'commit_docs': True,
                        'search_gitignored': False,
                        'branching_strategy': 'none',
                        'research': True,
                        'plan_checker': True,
                        'verifier': True,
                        'parallelization': True,
                    }
                    with open(config_path, 'w', encoding='utf-8') as f:
                        f.write(json.dumps(defaults, indent=2))
                    repair_actions.append({'action': repair, 'success': True, 'path': 'config.json'})

                elif repair == 'regenerateState':
                    if os.path.exists(state_path):
                        timestamp = datetime.now(timezone.utc).isoformat().replace(':', '-').replace('.', '-')[:19]
                        backup_path = '%s.bak-%s' % (state_path, timestamp)
                        shutil.copy2(state_path, backup_path)
                        repair_actions.append({'action': 'backupState', 'success': True, 'path': backup_path})

                    milestone = get_milestone_info(cwd)
                    today = datetime.now(timezone.utc).isoformat().split('T')[0]
                    state_content_new = '# Session State\n\n'
                    state_content_new += '## Project Reference\n\n'
                    state_content_new += 'See: .planning/PROJECT.md\n\n'
                    state_content_new += '## Position\n\n'
                    state_content_new += '**Milestone:** %s %s\n' % (milestone['version'], milestone['name'])
                    state_content_new += '**Current phase:** (determining...)\n'
                    state_content_new += '**Status:** Resuming\n\n'
                    state_content_new += '## Session Log\n\n'
                    state_content_new += '- %s: STATE.md regenerated by /gsd:health --repair\n' % today
                    write_state_md(state_path, state_content_new, cwd)
                    repair_actions.append({'action': repair, 'success': True, 'path': 'STATE.md'})

            except Exception as err:
                repair_actions.append({'action': repair, 'success': False, 'error': str(err)})

    if errors:
        status = 'broken'
    elif warnings:
        status = 'degraded'
    else:
        status = 'healthy'

    repairable_count = (
        len([e for e in errors if e.get('repairable')]) +
        len([w for w in warnings if w.get('repairable')])
    )

    result = {
        'status': status,
        'errors': errors,
        'warnings': warnings,
        'info': info,
        'repairable_count': repairable_count,
    }
    if repair_actions:
        result['repairs_performed'] = repair_actions

    output(result, raw)


def cmd_validate_agents(cwd, raw):
    """Validate GSD agent installation status."""
    from .core import check_agents_installed
    from .model_profiles import _all_profiles
    result = check_agents_installed()
    expected = list(_all_profiles().keys())
    result['expected'] = expected
    result['agents_found'] = result['agents_installed']
    output(result, raw)
