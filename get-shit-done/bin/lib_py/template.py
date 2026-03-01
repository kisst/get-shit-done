"""Template — Template selection and fill operations."""

import os
import re
from datetime import datetime, timezone

from .core import normalize_phase_name, find_phase_internal, generate_slug_internal, output, error
from .frontmatter import reconstruct_frontmatter


def cmd_template_select(cwd, plan_path, raw):
    if not plan_path:
        error('plan-path required')

    try:
        full_path = os.path.join(cwd, plan_path)
        with open(full_path, 'r', encoding='utf-8') as f:
            content = f.read()

        task_count = len(re.findall(r'###\s*Task\s*\d+', content))
        has_decisions = bool(re.search(r'decision', content, re.IGNORECASE))

        file_mentions = set()
        for m in re.finditer(r'`([^`]+\.[a-zA-Z]+)`', content):
            path = m.group(1)
            if '/' in path and not path.startswith('http'):
                file_mentions.add(path)
        file_count = len(file_mentions)

        template = 'templates/summary-standard.md'
        ttype = 'standard'

        if task_count <= 2 and file_count <= 3 and not has_decisions:
            template = 'templates/summary-minimal.md'
            ttype = 'minimal'
        elif has_decisions or file_count > 6 or task_count > 5:
            template = 'templates/summary-complex.md'
            ttype = 'complex'

        output({'template': template, 'type': ttype, 'taskCount': task_count, 'fileCount': file_count, 'hasDecisions': has_decisions}, raw, template)
    except Exception as e:
        output({'template': 'templates/summary-standard.md', 'type': 'standard', 'error': str(e)}, raw, 'templates/summary-standard.md')


def cmd_template_fill(cwd, template_type, options, raw):
    if not template_type:
        error('template type required: summary, plan, or verification')
    if not options.get('phase'):
        error('--phase required')

    phase_info = find_phase_internal(cwd, options['phase'])
    if not phase_info or not phase_info.get('found'):
        output({'error': 'Phase not found', 'phase': options['phase']}, raw)
        return

    padded = normalize_phase_name(options['phase'])
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    phase_name = options.get('name') or phase_info.get('phase_name') or 'Unnamed'
    phase_slug = phase_info.get('phase_slug') or generate_slug_internal(phase_name)
    phase_id = '%s-%s' % (padded, phase_slug)
    plan_num = (options.get('plan') or '01').zfill(2)
    fields = options.get('fields', {})

    if template_type == 'summary':
        frontmatter = {
            'phase': phase_id,
            'plan': plan_num,
            'subsystem': '[primary category]',
            'tags': [],
            'provides': [],
            'affects': [],
            'tech-stack': {'added': [], 'patterns': []},
            'key-files': {'created': [], 'modified': []},
            'key-decisions': [],
            'patterns-established': [],
            'duration': '[X]min',
            'completed': today,
        }
        frontmatter.update(fields)
        body = '\n'.join([
            '# Phase %s: %s Summary' % (options['phase'], phase_name),
            '', '**[Substantive one-liner describing outcome]**',
            '', '## Performance',
            '- **Duration:** [time]', '- **Tasks:** [count completed]', '- **Files modified:** [count]',
            '', '## Accomplishments', '- [Key outcome 1]', '- [Key outcome 2]',
            '', '## Task Commits', '1. **Task 1: [task name]** - `hash`',
            '', '## Files Created/Modified', '- `path/to/file.ts` - What it does',
            '', '## Decisions & Deviations', '[Key decisions or "None - followed plan as specified"]',
            '', '## Next Phase Readiness', "[What's ready for next phase]",
        ])
        file_name = '%s-%s-SUMMARY.md' % (padded, plan_num)

    elif template_type == 'plan':
        plan_type = options.get('type', 'execute')
        wave = int(options.get('wave', 1))
        frontmatter = {
            'phase': phase_id,
            'plan': plan_num,
            'type': plan_type,
            'wave': wave,
            'depends_on': [],
            'files_modified': [],
            'autonomous': True,
            'user_setup': [],
            'must_haves': {'truths': [], 'artifacts': [], 'key_links': []},
        }
        frontmatter.update(fields)
        body = '\n'.join([
            '# Phase %s Plan %s: [Title]' % (options['phase'], plan_num),
            '', '## Objective',
            '- **What:** [What this plan builds]',
            '- **Why:** [Why it matters for the phase goal]',
            '- **Output:** [Concrete deliverable]',
            '', '## Context', '@.planning/PROJECT.md', '@.planning/ROADMAP.md', '@.planning/STATE.md',
            '', '## Tasks', '',
            '<task type="code">',
            '  <name>[Task name]</name>',
            '  <files>[file paths]</files>',
            '  <action>[What to do]</action>',
            '  <verify>[How to verify]</verify>',
            '  <done>[Definition of done]</done>',
            '</task>',
            '', '## Verification', '[How to verify this plan achieved its objective]',
            '', '## Success Criteria', '- [ ] [Criterion 1]', '- [ ] [Criterion 2]',
        ])
        file_name = '%s-%s-PLAN.md' % (padded, plan_num)

    elif template_type == 'verification':
        frontmatter = {
            'phase': phase_id,
            'verified': datetime.now(timezone.utc).isoformat(),
            'status': 'pending',
            'score': '0/0 must-haves verified',
        }
        frontmatter.update(fields)
        body = '\n'.join([
            '# Phase %s: %s \u2014 Verification' % (options['phase'], phase_name),
            '', '## Observable Truths',
            '| # | Truth | Status | Evidence |', '|---|-------|--------|----------|',
            '| 1 | [Truth] | pending | |',
            '', '## Required Artifacts',
            '| Artifact | Expected | Status | Details |', '|----------|----------|--------|---------|',
            '| [path] | [what] | pending | |',
            '', '## Key Link Verification',
            '| From | To | Via | Status | Details |', '|------|----|----|--------|---------|',
            '| [source] | [target] | [connection] | pending | |',
            '', '## Requirements Coverage',
            '| Requirement | Status | Blocking Issue |', '|-------------|--------|----------------|',
            '| [req] | pending | |',
            '', '## Result', '[Pending verification]',
        ])
        file_name = '%s-VERIFICATION.md' % padded
    else:
        error('Unknown template type: %s. Available: summary, plan, verification' % template_type)
        return

    full_content = '---\n%s\n---\n\n%s\n' % (reconstruct_frontmatter(frontmatter), body)
    out_path = os.path.join(cwd, phase_info['directory'], file_name)

    if os.path.exists(out_path):
        output({'error': 'File already exists', 'path': os.path.relpath(out_path, cwd)}, raw)
        return

    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(full_content)
    rel_path = os.path.relpath(out_path, cwd)
    output({'created': True, 'path': rel_path, 'template': template_type}, raw, rel_path)
