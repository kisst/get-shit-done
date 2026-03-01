"""Milestone — Milestone and requirements lifecycle operations."""

import os
import re
from datetime import datetime, timezone

from .core import output, error
from .frontmatter import extract_frontmatter
from .state import write_state_md


def cmd_requirements_mark_complete(cwd, req_ids_raw, raw):
    if not req_ids_raw or len(req_ids_raw) == 0:
        error('requirement IDs required. Usage: requirements mark-complete REQ-01,REQ-02 or REQ-01 REQ-02')

    # Accept comma-separated, space-separated, or bracket-wrapped: [REQ-01, REQ-02]
    joined = ' '.join(req_ids_raw)
    joined = re.sub(r'[\[\]]', '', joined)
    req_ids = [r.strip() for r in re.split(r'[,\s]+', joined) if r.strip()]

    if len(req_ids) == 0:
        error('no valid requirement IDs found')

    req_path = os.path.join(cwd, '.planning', 'REQUIREMENTS.md')
    if not os.path.exists(req_path):
        output({'updated': False, 'reason': 'REQUIREMENTS.md not found', 'ids': req_ids}, raw, 'no requirements file')
        return

    with open(req_path, 'r', encoding='utf-8') as f:
        req_content = f.read()

    updated = []
    not_found = []

    for req_id in req_ids:
        found = False

        # Update checkbox: - [ ] **REQ-ID** → - [x] **REQ-ID**
        checkbox_pattern = re.compile(r'(-\s*\[)[ ](\]\s*\*\*%s\*\*)' % re.escape(req_id), re.IGNORECASE)
        if checkbox_pattern.search(req_content):
            req_content = checkbox_pattern.sub(r'\1x\2', req_content)
            found = True

        # Update traceability table: | REQ-ID | Phase N | Pending | → | REQ-ID | Phase N | Complete |
        table_pattern = re.compile(
            r'(\|\s*%s\s*\|[^|]+\|)\s*Pending\s*(\|)' % re.escape(req_id),
            re.IGNORECASE
        )
        if table_pattern.search(req_content):
            req_content = table_pattern.sub(r'\1 Complete \2', req_content)
            found = True

        if found:
            updated.append(req_id)
        else:
            not_found.append(req_id)

    if updated:
        with open(req_path, 'w', encoding='utf-8') as f:
            f.write(req_content)

    output({
        'updated': len(updated) > 0,
        'marked_complete': updated,
        'not_found': not_found,
        'total': len(req_ids),
    }, raw, '%s/%s requirements marked complete' % (len(updated), len(req_ids)))


def cmd_milestone_complete(cwd, version, options, raw):
    if not version:
        error('version required for milestone complete (e.g., v1.0)')

    roadmap_path = os.path.join(cwd, '.planning', 'ROADMAP.md')
    req_path = os.path.join(cwd, '.planning', 'REQUIREMENTS.md')
    state_path = os.path.join(cwd, '.planning', 'STATE.md')
    milestones_path = os.path.join(cwd, '.planning', 'MILESTONES.md')
    archive_dir = os.path.join(cwd, '.planning', 'milestones')
    phases_dir = os.path.join(cwd, '.planning', 'phases')
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    milestone_name = options.get('name') or version

    os.makedirs(archive_dir, exist_ok=True)

    # Extract milestone phase numbers from ROADMAP.md to scope stats.
    # Only phases listed in the current ROADMAP are counted — phases from
    # prior milestones that remain on disk are excluded.
    milestone_phase_nums = set()
    if os.path.exists(roadmap_path):
        try:
            with open(roadmap_path, 'r', encoding='utf-8') as f:
                roadmap_content = f.read()
            phase_pattern = re.compile(r'#{2,4}\s*Phase\s+(\d+[A-Z]?(?:\.\d+)*)\s*:', re.IGNORECASE)
            for phase_match in phase_pattern.finditer(roadmap_content):
                milestone_phase_nums.add(phase_match.group(1))
        except (IOError, OSError):
            pass

    # Pre-normalize phase numbers for O(1) lookup — strip leading zeros
    # and lowercase for case-insensitive matching of letter suffixes (e.g. 3A/3a).
    normalized_phase_nums = set(
        (num.lstrip('0') or '0').lower()
        for num in milestone_phase_nums
    )

    def is_dir_in_milestone(dir_name):
        """Match a phase directory to the milestone's phase set.

        Handles: "01-foo" -> "1", "3A-bar" -> "3a", "3.1-baz" -> "3.1"
        Returns False for non-phase directories (no leading digit).
        """
        if not normalized_phase_nums:
            return True  # no scoping
        m = re.match(r'^0*(\d+[A-Za-z]?(?:\.\d+)*)', dir_name)
        if not m:
            return False  # not a phase directory
        return m.group(1).lower() in normalized_phase_nums

    phase_count = 0
    total_plans = 0
    total_tasks = 0
    accomplishments = []

    try:
        entries = os.listdir(phases_dir)
        dirs = sorted([e for e in entries if os.path.isdir(os.path.join(phases_dir, e))])

        for dir_name in dirs:
            if not is_dir_in_milestone(dir_name):
                continue

            phase_count += 1
            phase_files = os.listdir(os.path.join(phases_dir, dir_name))
            plans = [f for f in phase_files if f.endswith('-PLAN.md') or f == 'PLAN.md']
            summaries = [f for f in phase_files if f.endswith('-SUMMARY.md') or f == 'SUMMARY.md']
            total_plans += len(plans)

            for s in summaries:
                try:
                    with open(os.path.join(phases_dir, dir_name, s), 'r', encoding='utf-8') as f:
                        summary_content = f.read()
                    fm = extract_frontmatter(summary_content)
                    if fm.get('one-liner'):
                        accomplishments.append(fm['one-liner'])
                    task_matches = re.findall(r'##\s*Task\s*\d+', summary_content, re.IGNORECASE)
                    total_tasks += len(task_matches)
                except (IOError, OSError):
                    pass
    except (IOError, OSError):
        pass

    # Archive ROADMAP.md
    if os.path.exists(roadmap_path):
        with open(roadmap_path, 'r', encoding='utf-8') as f:
            roadmap_file_content = f.read()
        with open(os.path.join(archive_dir, '%s-ROADMAP.md' % version), 'w', encoding='utf-8') as f:
            f.write(roadmap_file_content)

    # Archive REQUIREMENTS.md
    if os.path.exists(req_path):
        with open(req_path, 'r', encoding='utf-8') as f:
            req_content = f.read()
        archive_header = (
            '# Requirements Archive: %s %s\n\n'
            '**Archived:** %s\n'
            '**Status:** SHIPPED\n\n'
            'For current requirements, see `.planning/REQUIREMENTS.md`.\n\n'
            '---\n\n'
        ) % (version, milestone_name, today)
        with open(os.path.join(archive_dir, '%s-REQUIREMENTS.md' % version), 'w', encoding='utf-8') as f:
            f.write(archive_header + req_content)

    # Archive audit file if exists
    audit_file = os.path.join(cwd, '.planning', '%s-MILESTONE-AUDIT.md' % version)
    if os.path.exists(audit_file):
        os.rename(audit_file, os.path.join(archive_dir, '%s-MILESTONE-AUDIT.md' % version))

    # Create/append MILESTONES.md entry
    accomplishments_list = '\n'.join('- %s' % a for a in accomplishments)
    milestone_entry = (
        '## %s %s (Shipped: %s)\n\n'
        '**Phases completed:** %s phases, %s plans, %s tasks\n\n'
        '**Key accomplishments:**\n%s\n\n---\n\n'
    ) % (
        version, milestone_name, today,
        phase_count, total_plans, total_tasks,
        accomplishments_list or '- (none recorded)',
    )

    if os.path.exists(milestones_path):
        with open(milestones_path, 'r', encoding='utf-8') as f:
            existing = f.read()
        # Insert after header line(s) for reverse chronological order (newest first)
        header_match = re.match(r'^(#{1,3}\s+[^\n]*\n\n?)', existing)
        if header_match:
            header = header_match.group(1)
            rest = existing[len(header):]
            with open(milestones_path, 'w', encoding='utf-8') as f:
                f.write(header + milestone_entry + rest)
        else:
            with open(milestones_path, 'w', encoding='utf-8') as f:
                f.write(milestone_entry + existing)
    else:
        with open(milestones_path, 'w', encoding='utf-8') as f:
            f.write('# Milestones\n\n%s' % milestone_entry)

    # Update STATE.md
    if os.path.exists(state_path):
        with open(state_path, 'r', encoding='utf-8') as f:
            state_content = f.read()
        state_content = re.sub(
            r'(\*\*Status:\*\*\s*).*',
            lambda m: m.group(1) + '%s milestone complete' % version,
            state_content
        )
        state_content = re.sub(
            r'(\*\*Last Activity:\*\*\s*).*',
            lambda m: m.group(1) + today,
            state_content
        )
        state_content = re.sub(
            r'(\*\*Last Activity Description:\*\*\s*).*',
            lambda m: m.group(1) + '%s milestone completed and archived' % version,
            state_content
        )
        write_state_md(state_path, state_content, cwd)

    # Archive phase directories if requested
    phases_archived = False
    if options.get('archive_phases'):
        try:
            phase_archive_dir = os.path.join(archive_dir, '%s-phases' % version)
            os.makedirs(phase_archive_dir, exist_ok=True)

            phase_entries = os.listdir(phases_dir)
            phase_dir_names = [e for e in phase_entries if os.path.isdir(os.path.join(phases_dir, e))]
            archived_count = 0
            for dir_name in phase_dir_names:
                if not is_dir_in_milestone(dir_name):
                    continue
                os.rename(
                    os.path.join(phases_dir, dir_name),
                    os.path.join(phase_archive_dir, dir_name)
                )
                archived_count += 1
            phases_archived = archived_count > 0
        except (IOError, OSError):
            pass

    result = {
        'version': version,
        'name': milestone_name,
        'date': today,
        'phases': phase_count,
        'plans': total_plans,
        'tasks': total_tasks,
        'accomplishments': accomplishments,
        'archived': {
            'roadmap': os.path.exists(os.path.join(archive_dir, '%s-ROADMAP.md' % version)),
            'requirements': os.path.exists(os.path.join(archive_dir, '%s-REQUIREMENTS.md' % version)),
            'audit': os.path.exists(os.path.join(archive_dir, '%s-MILESTONE-AUDIT.md' % version)),
            'phases': phases_archived,
        },
        'milestones_updated': True,
        'state_updated': os.path.exists(state_path),
    }

    output(result, raw)
