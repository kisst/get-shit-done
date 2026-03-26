"""Phase — Phase CRUD, query, and lifecycle operations."""

import os
import re
import shutil
from datetime import datetime, timezone

from .core import (
    normalize_phase_name,
    compare_phase_num,
    find_phase_internal,
    escape_regex,
    generate_slug_internal,
    get_archived_phase_dirs,
    output,
    error,
    _phase_sort_key,
)
from .frontmatter import extract_frontmatter
from .state import write_state_md


def cmd_phases_list(cwd, options, raw):
    phases_dir = os.path.join(cwd, '.planning', 'phases')
    file_type = options.get('type')
    phase = options.get('phase')
    include_archived = options.get('includeArchived', False)

    if not os.path.exists(phases_dir):
        if file_type:
            output({'files': [], 'count': 0}, raw, '')
        else:
            output({'directories': [], 'count': 0}, raw, '')
        return

    try:
        entries = os.listdir(phases_dir)
        dirs = sorted(
            [e for e in entries if os.path.isdir(os.path.join(phases_dir, e))],
            key=_phase_sort_key,
        )

        if include_archived:
            archived = get_archived_phase_dirs(cwd)
            for a in archived:
                dirs.append('%s [%s]' % (a['name'], a['milestone']))

        if phase:
            normalized = normalize_phase_name(phase)
            match = next((d for d in dirs if d.startswith(normalized)), None)
            if not match:
                output({'files': [], 'count': 0, 'phase_dir': None, 'error': 'Phase not found'}, raw, '')
                return
            dirs = [match]

        if file_type:
            files = []
            for d in dirs:
                dir_path = os.path.join(phases_dir, d)
                dir_files = os.listdir(dir_path)

                if file_type == 'plans':
                    filtered = [f for f in dir_files if f.endswith('-PLAN.md') or f == 'PLAN.md']
                elif file_type == 'summaries':
                    filtered = [f for f in dir_files if f.endswith('-SUMMARY.md') or f == 'SUMMARY.md']
                else:
                    filtered = dir_files

                files.extend(sorted(filtered))

            phase_dir_val = None
            if phase and dirs:
                phase_dir_val = re.sub(r'^\d+(?:\.\d+)*-?', '', dirs[0])
            result = {
                'files': files,
                'count': len(files),
                'phase_dir': phase_dir_val,
            }
            output(result, raw, '\n'.join(files))
            return

        output({'directories': dirs, 'count': len(dirs)}, raw, '\n'.join(dirs))
    except (IOError, OSError) as e:
        error('Failed to list phases: ' + str(e))


def cmd_phase_next_decimal(cwd, base_phase, raw):
    phases_dir = os.path.join(cwd, '.planning', 'phases')
    normalized = normalize_phase_name(base_phase)

    if not os.path.exists(phases_dir):
        next_val = '%s.1' % normalized
        output(
            {
                'found': False,
                'base_phase': normalized,
                'next': next_val,
                'existing': [],
            },
            raw,
            next_val,
        )
        return

    try:
        entries = os.listdir(phases_dir)
        dirs = [e for e in entries if os.path.isdir(os.path.join(phases_dir, e))]

        base_exists = any(d.startswith(normalized + '-') or d == normalized for d in dirs)

        decimal_pattern = re.compile(r'^%s\.(\d+)' % re.escape(normalized))
        existing_decimals = []
        for d in dirs:
            m = decimal_pattern.match(d)
            if m:
                existing_decimals.append('%s.%s' % (normalized, m.group(1)))

        existing_decimals.sort(key=_phase_sort_key)

        if not existing_decimals:
            next_decimal = '%s.1' % normalized
        else:
            last_decimal = existing_decimals[-1]
            last_num = int(last_decimal.split('.')[-1])
            next_decimal = '%s.%d' % (normalized, last_num + 1)

        output(
            {
                'found': base_exists,
                'base_phase': normalized,
                'next': next_decimal,
                'existing': existing_decimals,
            },
            raw,
            next_decimal,
        )
    except (IOError, OSError) as e:
        error('Failed to calculate next decimal phase: ' + str(e))


def cmd_find_phase(cwd, phase, raw):
    if not phase:
        error('phase identifier required')

    phases_dir = os.path.join(cwd, '.planning', 'phases')
    normalized = normalize_phase_name(phase)

    not_found = {'found': False, 'directory': None, 'phase_number': None, 'phase_name': None, 'plans': [], 'summaries': []}

    try:
        entries = os.listdir(phases_dir)
        dirs = sorted(
            [e for e in entries if os.path.isdir(os.path.join(phases_dir, e))],
            key=_phase_sort_key,
        )

        match = next((d for d in dirs if d.startswith(normalized)), None)
        if not match:
            output(not_found, raw, '')
            return

        dir_match = re.match(r'^(\d+[A-Z]?(?:\.\d+)*)-?(.*)', match, re.IGNORECASE)
        phase_number = dir_match.group(1) if dir_match else normalized
        phase_name = dir_match.group(2) if dir_match and dir_match.group(2) else None

        phase_dir = os.path.join(phases_dir, match)
        phase_files = os.listdir(phase_dir)
        plans = sorted([f for f in phase_files if f.endswith('-PLAN.md') or f == 'PLAN.md'])
        summaries = sorted([f for f in phase_files if f.endswith('-SUMMARY.md') or f == 'SUMMARY.md'])

        result = {
            'found': True,
            'directory': os.path.join('.planning', 'phases', match).replace(os.sep, '/'),
            'phase_number': phase_number,
            'phase_name': phase_name,
            'plans': plans,
            'summaries': summaries,
        }

        output(result, raw, result['directory'])
    except (IOError, OSError):
        output(not_found, raw, '')


def _extract_objective(content):
    m = re.search(r'<objective>\s*\n?\s*(.+)', content)
    return m.group(1).strip() if m else None


def cmd_phase_plan_index(cwd, phase, raw):
    if not phase:
        error('phase required for phase-plan-index')

    phases_dir = os.path.join(cwd, '.planning', 'phases')
    normalized = normalize_phase_name(phase)

    phase_dir = None
    phase_dir_name = None
    try:
        entries = os.listdir(phases_dir)
        dirs = sorted(
            [e for e in entries if os.path.isdir(os.path.join(phases_dir, e))],
            key=_phase_sort_key,
        )
        match = next((d for d in dirs if d.startswith(normalized)), None)
        if match:
            phase_dir = os.path.join(phases_dir, match)
            phase_dir_name = match
    except (IOError, OSError):
        pass

    if not phase_dir:
        output({'phase': normalized, 'error': 'Phase not found', 'plans': [], 'waves': {}, 'incomplete': [], 'has_checkpoints': False}, raw)
        return

    phase_files = os.listdir(phase_dir)
    plan_files = sorted([f for f in phase_files if f.endswith('-PLAN.md') or f == 'PLAN.md'])
    summary_files = [f for f in phase_files if f.endswith('-SUMMARY.md') or f == 'SUMMARY.md']

    completed_plan_ids = set(
        s.replace('-SUMMARY.md', '').replace('SUMMARY.md', '') for s in summary_files
    )

    plans = []
    waves = {}
    incomplete = []
    has_checkpoints = False

    for plan_file in plan_files:
        plan_id = plan_file.replace('-PLAN.md', '').replace('PLAN.md', '')
        plan_path = os.path.join(phase_dir, plan_file)
        with open(plan_path, 'r', encoding='utf-8') as f:
            content = f.read()
        fm = extract_frontmatter(content)

        xml_tasks = re.findall(r'<task[\s>]', content, re.IGNORECASE)
        md_tasks = re.findall(r'##\s*Task\s*\d+', content, re.IGNORECASE)
        task_count = len(xml_tasks) or len(md_tasks)

        wave = int(fm.get('wave', 1) or 1)
        try:
            wave = int(fm.get('wave', 1))
        except (ValueError, TypeError):
            wave = 1

        autonomous = True
        fm_autonomous = fm.get('autonomous')
        if fm_autonomous is not None:
            autonomous = fm_autonomous == 'true' or fm_autonomous is True

        if not autonomous:
            has_checkpoints = True

        files_modified = []
        fm_files = fm.get('files_modified') or fm.get('files-modified')
        if fm_files:
            files_modified = fm_files if isinstance(fm_files, list) else [fm_files]

        has_summary = plan_id in completed_plan_ids
        if not has_summary:
            incomplete.append(plan_id)

        plan = {
            'id': plan_id,
            'wave': wave,
            'autonomous': autonomous,
            'objective': _extract_objective(content) or fm.get('objective') or None,
            'files_modified': files_modified,
            'task_count': task_count,
            'has_summary': has_summary,
        }

        plans.append(plan)

        wave_key = str(wave)
        if wave_key not in waves:
            waves[wave_key] = []
        waves[wave_key].append(plan_id)

    result = {
        'phase': normalized,
        'plans': plans,
        'waves': waves,
        'incomplete': incomplete,
        'has_checkpoints': has_checkpoints,
    }

    output(result, raw)


def cmd_phase_add(cwd, description, raw, custom_id=None):
    if not description:
        error('description required for phase add')

    roadmap_path = os.path.join(cwd, '.planning', 'ROADMAP.md')
    if not os.path.exists(roadmap_path):
        error('ROADMAP.md not found')

    with open(roadmap_path, 'r', encoding='utf-8') as f:
        content = f.read()

    slug = generate_slug_internal(description)

    # Support custom IDs (e.g., PROJ-42) via --id flag
    if custom_id:
        new_phase_num = custom_id
    else:
        # Find highest integer phase in current milestone only
        from .core import extract_current_milestone
        milestone_content = extract_current_milestone(content, cwd)
        phase_pattern = re.compile(r'#{2,4}\s*Phase\s+(\d+)[A-Z]?(?:\.\d+)*:', re.IGNORECASE)
        max_phase = 0
        for m in phase_pattern.finditer(milestone_content):
            num = int(m.group(1))
            if num > max_phase:
                max_phase = num
        new_phase_num = max_phase + 1
    padded_num = str(new_phase_num).zfill(2)
    dir_name = '%s-%s' % (padded_num, slug)
    dir_path = os.path.join(cwd, '.planning', 'phases', dir_name)

    os.makedirs(dir_path, exist_ok=True)
    with open(os.path.join(dir_path, '.gitkeep'), 'w') as f:
        f.write('')

    phase_entry = (
        '\n### Phase %d: %s\n\n'
        '**Goal:** [To be planned]\n'
        '**Requirements**: TBD\n'
        '**Depends on:** Phase %d\n'
        '**Plans:** 0 plans\n\n'
        'Plans:\n'
        '- [ ] TBD (run /gsd:plan-phase %d to break down)\n'
    ) % (new_phase_num, description, max_phase, new_phase_num)

    last_separator = content.rfind('\n---')
    if last_separator > 0:
        updated_content = content[:last_separator] + phase_entry + content[last_separator:]
    else:
        updated_content = content + phase_entry

    with open(roadmap_path, 'w', encoding='utf-8') as f:
        f.write(updated_content)

    result = {
        'phase_number': new_phase_num,
        'padded': padded_num,
        'name': description,
        'slug': slug,
        'directory': '.planning/phases/%s' % dir_name,
        'naming_mode': 'custom' if custom_id else 'sequential',
    }

    output(result, raw, padded_num)


def cmd_phase_insert(cwd, after_phase, description, raw):
    if not after_phase or not description:
        error('after-phase and description required for phase insert')

    roadmap_path = os.path.join(cwd, '.planning', 'ROADMAP.md')
    if not os.path.exists(roadmap_path):
        error('ROADMAP.md not found')

    with open(roadmap_path, 'r', encoding='utf-8') as f:
        content = f.read()

    slug = generate_slug_internal(description)

    normalized_after = normalize_phase_name(after_phase)
    unpadded = re.sub(r'^0+', '', normalized_after)
    after_phase_escaped = unpadded.replace('.', r'\.')
    target_pattern = re.compile(r'#{2,4}\s*Phase\s+0*%s:' % after_phase_escaped, re.IGNORECASE)
    if not target_pattern.search(content):
        error('Phase %s not found in ROADMAP.md' % after_phase)

    phases_dir = os.path.join(cwd, '.planning', 'phases')
    normalized_base = normalize_phase_name(after_phase)
    existing_decimals = []

    try:
        entries = os.listdir(phases_dir)
        dirs = [e for e in entries if os.path.isdir(os.path.join(phases_dir, e))]
        decimal_pattern = re.compile(r'^%s\.(\d+)' % re.escape(normalized_base))
        for d in dirs:
            dm = decimal_pattern.match(d)
            if dm:
                existing_decimals.append(int(dm.group(1)))
    except (IOError, OSError):
        pass

    next_decimal = 1 if not existing_decimals else max(existing_decimals) + 1
    decimal_phase = '%s.%d' % (normalized_base, next_decimal)
    dir_name = '%s-%s' % (decimal_phase, slug)
    dir_path = os.path.join(phases_dir, dir_name)

    os.makedirs(dir_path, exist_ok=True)
    with open(os.path.join(dir_path, '.gitkeep'), 'w') as f:
        f.write('')

    phase_entry = (
        '\n### Phase %s: %s (INSERTED)\n\n'
        '**Goal:** [Urgent work - to be planned]\n'
        '**Requirements**: TBD\n'
        '**Depends on:** Phase %s\n'
        '**Plans:** 0 plans\n\n'
        'Plans:\n'
        '- [ ] TBD (run /gsd:plan-phase %s to break down)\n'
    ) % (decimal_phase, description, after_phase, decimal_phase)

    header_pattern = re.compile(r'(#{2,4}\s*Phase\s+0*%s:[^\n]*\n)' % after_phase_escaped, re.IGNORECASE)
    header_match = header_pattern.search(content)
    if not header_match:
        error('Could not find Phase %s header' % after_phase)

    header_idx = header_match.start()
    after_header = content[header_idx + len(header_match.group(0)):]
    next_phase_match = re.search(r'\n#{2,4}\s+Phase\s+\d', after_header, re.IGNORECASE)

    if next_phase_match:
        insert_idx = header_idx + len(header_match.group(0)) + next_phase_match.start()
    else:
        insert_idx = len(content)

    updated_content = content[:insert_idx] + phase_entry + content[insert_idx:]
    with open(roadmap_path, 'w', encoding='utf-8') as f:
        f.write(updated_content)

    result = {
        'phase_number': decimal_phase,
        'after_phase': after_phase,
        'name': description,
        'slug': slug,
        'directory': '.planning/phases/%s' % dir_name,
    }

    output(result, raw, decimal_phase)


def cmd_phase_remove(cwd, target_phase, options, raw):
    if not target_phase:
        error('phase number required for phase remove')

    roadmap_path = os.path.join(cwd, '.planning', 'ROADMAP.md')
    phases_dir = os.path.join(cwd, '.planning', 'phases')
    force = options.get('force', False)

    if not os.path.exists(roadmap_path):
        error('ROADMAP.md not found')

    normalized = normalize_phase_name(target_phase)
    is_decimal = '.' in str(target_phase)

    target_dir = None
    try:
        entries = os.listdir(phases_dir)
        dirs = sorted(
            [e for e in entries if os.path.isdir(os.path.join(phases_dir, e))],
            key=_phase_sort_key,
        )
        target_dir = next(
            (d for d in dirs if d.startswith(normalized + '-') or d == normalized),
            None,
        )
    except (IOError, OSError):
        pass

    if target_dir and not force:
        target_path = os.path.join(phases_dir, target_dir)
        files = os.listdir(target_path)
        summaries = [f for f in files if f.endswith('-SUMMARY.md') or f == 'SUMMARY.md']
        if summaries:
            error('Phase %s has %d executed plan(s). Use --force to remove anyway.' % (target_phase, len(summaries)))

    if target_dir:
        shutil.rmtree(os.path.join(phases_dir, target_dir), ignore_errors=True)

    renamed_dirs = []
    renamed_files = []

    if is_decimal:
        base_parts = normalized.split('.')
        base_int = base_parts[0]
        removed_decimal = int(base_parts[1])

        try:
            entries = os.listdir(phases_dir)
            dirs = sorted(
                [e for e in entries if os.path.isdir(os.path.join(phases_dir, e))],
                key=_phase_sort_key,
            )

            dec_pattern = re.compile(r'^%s\.(\d+)-(.+)$' % re.escape(base_int))
            to_rename = []
            for d in dirs:
                dm = dec_pattern.match(d)
                if dm and int(dm.group(1)) > removed_decimal:
                    to_rename.append({'dir': d, 'oldDecimal': int(dm.group(1)), 'slug': dm.group(2)})

            to_rename.sort(key=lambda x: x['oldDecimal'], reverse=True)

            for item in to_rename:
                new_decimal = item['oldDecimal'] - 1
                old_phase_id = '%s.%d' % (base_int, item['oldDecimal'])
                new_phase_id = '%s.%d' % (base_int, new_decimal)
                new_dir_name = '%s.%d-%s' % (base_int, new_decimal, item['slug'])

                os.rename(
                    os.path.join(phases_dir, item['dir']),
                    os.path.join(phases_dir, new_dir_name),
                )
                renamed_dirs.append({'from': item['dir'], 'to': new_dir_name})

                dir_files = os.listdir(os.path.join(phases_dir, new_dir_name))
                for f in dir_files:
                    if old_phase_id in f:
                        new_file_name = f.replace(old_phase_id, new_phase_id)
                        os.rename(
                            os.path.join(phases_dir, new_dir_name, f),
                            os.path.join(phases_dir, new_dir_name, new_file_name),
                        )
                        renamed_files.append({'from': f, 'to': new_file_name})
        except (IOError, OSError):
            pass

    else:
        removed_int = int(normalized)

        try:
            entries = os.listdir(phases_dir)
            dirs = sorted(
                [e for e in entries if os.path.isdir(os.path.join(phases_dir, e))],
                key=_phase_sort_key,
            )

            to_rename = []
            for d in dirs:
                dm = re.match(r'^(\d+)([A-Z])?(?:\.(\d+))?-(.+)$', d, re.IGNORECASE)
                if not dm:
                    continue
                dir_int = int(dm.group(1))
                if dir_int > removed_int:
                    to_rename.append({
                        'dir': d,
                        'oldInt': dir_int,
                        'letter': dm.group(2).upper() if dm.group(2) else '',
                        'decimal': int(dm.group(3)) if dm.group(3) else None,
                        'slug': dm.group(4),
                    })

            def sort_key_desc(x):
                return (-x['oldInt'], -(x['decimal'] or 0))

            to_rename.sort(key=sort_key_desc)

            for item in to_rename:
                new_int = item['oldInt'] - 1
                new_padded = str(new_int).zfill(2)
                old_padded = str(item['oldInt']).zfill(2)
                letter_suffix = item['letter']
                decimal_suffix = '.%d' % item['decimal'] if item['decimal'] is not None else ''
                old_prefix = '%s%s%s' % (old_padded, letter_suffix, decimal_suffix)
                new_prefix = '%s%s%s' % (new_padded, letter_suffix, decimal_suffix)
                new_dir_name = '%s-%s' % (new_prefix, item['slug'])

                os.rename(
                    os.path.join(phases_dir, item['dir']),
                    os.path.join(phases_dir, new_dir_name),
                )
                renamed_dirs.append({'from': item['dir'], 'to': new_dir_name})

                dir_files = os.listdir(os.path.join(phases_dir, new_dir_name))
                for f in dir_files:
                    if f.startswith(old_prefix):
                        new_file_name = new_prefix + f[len(old_prefix):]
                        os.rename(
                            os.path.join(phases_dir, new_dir_name, f),
                            os.path.join(phases_dir, new_dir_name, new_file_name),
                        )
                        renamed_files.append({'from': f, 'to': new_file_name})
        except (IOError, OSError):
            pass

    with open(roadmap_path, 'r', encoding='utf-8') as f:
        roadmap_content = f.read()

    target_escaped = escape_regex(target_phase)
    section_pattern = re.compile(
        r'\n?#{2,4}\s*Phase\s+%s\s*:[\s\S]*?(?=\n#{2,4}\s+Phase\s+\d|$)' % target_escaped,
        re.IGNORECASE,
    )
    roadmap_content = section_pattern.sub('', roadmap_content)

    checkbox_pattern = re.compile(
        r'\n?-\s*\[[ x]\]\s*.*Phase\s+%s[:\s][^\n]*' % target_escaped,
        re.IGNORECASE,
    )
    roadmap_content = checkbox_pattern.sub('', roadmap_content)

    table_row_pattern = re.compile(
        r'\n?\|\s*%s\.?\s[^|]*\|[^\n]*' % target_escaped,
        re.IGNORECASE,
    )
    roadmap_content = table_row_pattern.sub('', roadmap_content)

    if not is_decimal:
        removed_int = int(normalized)
        max_phase = 99
        for old_num in range(max_phase, removed_int, -1):
            new_num = old_num - 1
            old_str = str(old_num)
            new_str = str(new_num)
            old_pad = old_str.zfill(2)
            new_pad = new_str.zfill(2)

            roadmap_content = re.sub(
                r'(#{2,4}\s*Phase\s+)%s(\s*:)' % old_str,
                lambda m, ns=new_str: m.group(1) + ns + m.group(2),
                roadmap_content,
                flags=re.IGNORECASE,
            )

            roadmap_content = re.sub(
                r'(Phase\s+)%s([:\s])' % old_str,
                lambda m, ns=new_str: m.group(1) + ns + m.group(2),
                roadmap_content,
            )

            roadmap_content = re.sub(
                r'%s-(\d{2})' % old_pad,
                lambda m, np=new_pad: np + '-' + m.group(1),
                roadmap_content,
            )

            roadmap_content = re.sub(
                r'(\|\s*)%s\.\s' % old_str,
                lambda m, ns=new_str: m.group(1) + ns + '. ',
                roadmap_content,
            )

            roadmap_content = re.sub(
                r'(Depends on:\*\*\s*Phase\s+)%s\b' % old_str,
                lambda m, ns=new_str: m.group(1) + ns,
                roadmap_content,
                flags=re.IGNORECASE,
            )

    with open(roadmap_path, 'w', encoding='utf-8') as f:
        f.write(roadmap_content)

    state_path = os.path.join(cwd, '.planning', 'STATE.md')
    if os.path.exists(state_path):
        with open(state_path, 'r', encoding='utf-8') as f:
            state_content = f.read()

        total_pattern = re.compile(r'(\*\*Total Phases:\*\*\s*)(\d+)')
        total_match = total_pattern.search(state_content)
        if total_match:
            old_total = int(total_match.group(2))
            state_content = total_pattern.sub(
                lambda m, t=old_total: m.group(1) + str(t - 1),
                state_content,
            )

        of_pattern = re.compile(r'(\bof\s+)(\d+)(\s*(?:\(|phases?))', re.IGNORECASE)
        of_match = of_pattern.search(state_content)
        if of_match:
            old_total = int(of_match.group(2))
            state_content = of_pattern.sub(
                lambda m, t=old_total: m.group(1) + str(t - 1) + m.group(3),
                state_content,
            )

        write_state_md(state_path, state_content, cwd)

    result = {
        'removed': target_phase,
        'directory_deleted': target_dir or None,
        'renamed_directories': renamed_dirs,
        'renamed_files': renamed_files,
        'roadmap_updated': True,
        'state_updated': os.path.exists(state_path),
    }

    output(result, raw)


def cmd_phase_complete(cwd, phase_num, raw):
    if not phase_num:
        error('phase number required for phase complete')

    roadmap_path = os.path.join(cwd, '.planning', 'ROADMAP.md')
    state_path = os.path.join(cwd, '.planning', 'STATE.md')
    phases_dir = os.path.join(cwd, '.planning', 'phases')
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')

    phase_info = find_phase_internal(cwd, phase_num)
    if not phase_info:
        error('Phase %s not found' % phase_num)

    plan_count = len(phase_info['plans'])
    summary_count = len(phase_info['summaries'])

    if os.path.exists(roadmap_path):
        with open(roadmap_path, 'r', encoding='utf-8') as f:
            roadmap_content = f.read()

        checkbox_pattern = re.compile(
            r'(-\s*\[)[ ](\]\s*.*Phase\s+%s[:\s][^\n]*)' % escape_regex(phase_num),
            re.IGNORECASE,
        )
        roadmap_content = checkbox_pattern.sub(
            lambda m: m.group(1) + 'x' + m.group(2) + ' (completed %s)' % today,
            roadmap_content,
        )

        phase_escaped = escape_regex(phase_num)
        table_pattern = re.compile(
            r'(\|\s*%s\.?\s[^|]*\|[^|]*\|)\s*[^|]*(\|)\s*[^|]*(\|)' % phase_escaped,
            re.IGNORECASE,
        )
        roadmap_content = table_pattern.sub(
            lambda m: m.group(1) + ' Complete    ' + m.group(2) + ' %s ' % today + m.group(3),
            roadmap_content,
        )

        plan_count_pattern = re.compile(
            r'(#{2,4}\s*Phase\s+%s[\s\S]*?\*\*Plans:\*\*\s*)[^\n]+' % phase_escaped,
            re.IGNORECASE,
        )
        roadmap_content = plan_count_pattern.sub(
            lambda m: m.group(1) + '%d/%d plans complete' % (summary_count, plan_count),
            roadmap_content,
        )

        with open(roadmap_path, 'w', encoding='utf-8') as f:
            f.write(roadmap_content)

        req_path = os.path.join(cwd, '.planning', 'REQUIREMENTS.md')
        if os.path.exists(req_path):
            req_match = re.search(
                r'Phase\s+%s[\s\S]*?\*\*Requirements:\*\*\s*([^\n]+)' % escape_regex(phase_num),
                roadmap_content,
                re.IGNORECASE,
            )

            if req_match:
                req_ids_raw = re.sub(r'[\[\]]', '', req_match.group(1))
                req_ids = [r.strip() for r in re.split(r'[,\s]+', req_ids_raw) if r.strip()]

                with open(req_path, 'r', encoding='utf-8') as f:
                    req_content = f.read()

                for req_id in req_ids:
                    req_escaped = escape_regex(req_id)
                    req_content = re.sub(
                        r'(-\s*\[)[ ](\]\s*\*\*%s\*\*)' % req_escaped,
                        r'\1x\2',
                        req_content,
                        flags=re.IGNORECASE,
                    )
                    req_content = re.sub(
                        r'(\|\s*%s\s*\|[^|]+\|)\s*Pending\s*(\|)' % req_escaped,
                        r'\1 Complete \2',
                        req_content,
                        flags=re.IGNORECASE,
                    )

                with open(req_path, 'w', encoding='utf-8') as f:
                    f.write(req_content)

    next_phase_num = None
    next_phase_name = None
    is_last_phase = True

    try:
        entries = os.listdir(phases_dir)
        dirs = sorted(
            [e for e in entries if os.path.isdir(os.path.join(phases_dir, e))],
            key=_phase_sort_key,
        )

        for d in dirs:
            dm = re.match(r'^(\d+[A-Z]?(?:\.\d+)*)-?(.*)', d, re.IGNORECASE)
            if dm:
                if compare_phase_num(dm.group(1), phase_num) > 0:
                    next_phase_num = dm.group(1)
                    next_phase_name = dm.group(2) or None
                    is_last_phase = False
                    break
    except (IOError, OSError):
        pass

    if os.path.exists(state_path):
        with open(state_path, 'r', encoding='utf-8') as f:
            state_content = f.read()

        state_content = re.sub(
            r'(\*\*Current Phase:\*\*\s*).*',
            lambda m: m.group(1) + (next_phase_num or phase_num),
            state_content,
        )

        if next_phase_name:
            state_content = re.sub(
                r'(\*\*Current Phase Name:\*\*\s*).*',
                lambda m: m.group(1) + next_phase_name.replace('-', ' '),
                state_content,
            )

        state_content = re.sub(
            r'(\*\*Status:\*\*\s*).*',
            lambda m: m.group(1) + ('Milestone complete' if is_last_phase else 'Ready to plan'),
            state_content,
        )

        state_content = re.sub(
            r'(\*\*Current Plan:\*\*\s*).*',
            lambda m: m.group(1) + 'Not started',
            state_content,
        )

        state_content = re.sub(
            r'(\*\*Last Activity:\*\*\s*).*',
            lambda m: m.group(1) + today,
            state_content,
        )

        desc = 'Phase %s complete' % phase_num
        if next_phase_num:
            desc += ', transitioned to Phase %s' % next_phase_num
        state_content = re.sub(
            r'(\*\*Last Activity Description:\*\*\s*).*',
            lambda m: m.group(1) + desc,
            state_content,
        )

        write_state_md(state_path, state_content, cwd)

    result = {
        'completed_phase': phase_num,
        'phase_name': phase_info.get('phase_name'),
        'plans_executed': '%d/%d' % (summary_count, plan_count),
        'next_phase': next_phase_num,
        'next_phase_name': next_phase_name,
        'is_last_phase': is_last_phase,
        'date': today,
        'roadmap_updated': os.path.exists(roadmap_path),
        'state_updated': os.path.exists(state_path),
    }

    output(result, raw)
