"""Commands — Standalone utility commands."""

import json
import os
import re
import sys
from datetime import datetime, timezone

from .core import (
    safe_read_file, load_config, is_git_ignored, exec_git,
    normalize_phase_name, compare_phase_num, get_archived_phase_dirs,
    generate_slug_internal, get_milestone_info, resolve_model_internal,
    MODEL_PROFILES, output, error, find_phase_internal, _phase_sort_key,
)
from .frontmatter import extract_frontmatter


def cmd_generate_slug(text, raw):
    if not text:
        error('text required for slug generation')
    slug = re.sub(r'^-+|-+$', '', re.sub(r'[^a-z0-9]+', '-', text.lower()))
    output({'slug': slug}, raw, slug)


def cmd_current_timestamp(fmt, raw):
    now = datetime.now(timezone.utc)
    if fmt == 'date':
        result = now.strftime('%Y-%m-%d')
    elif fmt == 'filename':
        result = now.strftime('%Y-%m-%dT%H-%M-%S')
    else:
        result = now.strftime('%Y-%m-%dT%H:%M:%S.') + '%03dZ' % (now.microsecond // 1000)
    output({'timestamp': result}, raw, result)


def cmd_list_todos(cwd, area, raw):
    pending_dir = os.path.join(cwd, '.planning', 'todos', 'pending')
    count = 0
    todos = []

    try:
        files = sorted([f for f in os.listdir(pending_dir) if f.endswith('.md')])
        for fname in files:
            try:
                with open(os.path.join(pending_dir, fname), 'r', encoding='utf-8') as f:
                    content = f.read()
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
                    'path': os.path.join('.planning', 'todos', 'pending', fname),
                })
            except (IOError, OSError):
                pass
    except (IOError, OSError):
        pass

    output({'count': count, 'todos': todos}, raw, str(count))


def cmd_verify_path_exists(cwd, target_path, raw):
    if not target_path:
        error('path required for verification')
    full_path = target_path if os.path.isabs(target_path) else os.path.join(cwd, target_path)
    try:
        st = os.stat(full_path)
        if os.path.isdir(full_path):
            ftype = 'directory'
        elif os.path.isfile(full_path):
            ftype = 'file'
        else:
            ftype = 'other'
        output({'exists': True, 'type': ftype}, raw, 'true')
    except (IOError, OSError):
        output({'exists': False, 'type': None}, raw, 'false')


def cmd_history_digest(cwd, raw):
    phases_dir = os.path.join(cwd, '.planning', 'phases')
    digest = {'phases': {}, 'decisions': [], 'tech_stack': set()}

    all_phase_dirs = []

    archived = get_archived_phase_dirs(cwd)
    for a in archived:
        all_phase_dirs.append({'name': a['name'], 'fullPath': a['fullPath'], 'milestone': a['milestone']})

    if os.path.exists(phases_dir):
        try:
            current_dirs = sorted(
                [e for e in os.listdir(phases_dir) if os.path.isdir(os.path.join(phases_dir, e))]
            )
            for d in current_dirs:
                all_phase_dirs.append({'name': d, 'fullPath': os.path.join(phases_dir, d), 'milestone': None})
        except (IOError, OSError):
            pass

    if not all_phase_dirs:
        digest['tech_stack'] = []
        output(digest, raw)
        return

    try:
        for entry in all_phase_dirs:
            dir_path = entry['fullPath']
            try:
                files_in_dir = os.listdir(dir_path)
            except (IOError, OSError):
                continue
            summaries = [f for f in files_in_dir if f.endswith('-SUMMARY.md') or f == 'SUMMARY.md']

            for summary in summaries:
                try:
                    with open(os.path.join(dir_path, summary), 'r', encoding='utf-8') as f:
                        content = f.read()
                    fm = extract_frontmatter(content)
                    phase_num = fm.get('phase', entry['name'].split('-')[0])

                    if phase_num not in digest['phases']:
                        name_parts = entry['name'].split('-')[1:]
                        digest['phases'][phase_num] = {
                            'name': fm.get('name', ' '.join(name_parts) if name_parts else 'Unknown'),
                            'provides': set(),
                            'affects': set(),
                            'patterns': set(),
                        }

                    phase_data = digest['phases'][phase_num]

                    dep_graph = fm.get('dependency-graph', {})
                    if isinstance(dep_graph, dict) and dep_graph.get('provides'):
                        for p in dep_graph['provides']:
                            phase_data['provides'].add(p)
                    elif fm.get('provides') and isinstance(fm['provides'], list):
                        for p in fm['provides']:
                            phase_data['provides'].add(p)

                    if isinstance(dep_graph, dict) and dep_graph.get('affects'):
                        for a in dep_graph['affects']:
                            phase_data['affects'].add(a)

                    if fm.get('patterns-established') and isinstance(fm['patterns-established'], list):
                        for p in fm['patterns-established']:
                            phase_data['patterns'].add(p)

                    if fm.get('key-decisions') and isinstance(fm['key-decisions'], list):
                        for d in fm['key-decisions']:
                            digest['decisions'].append({'phase': phase_num, 'decision': d})

                    tech = fm.get('tech-stack', {})
                    if isinstance(tech, dict) and tech.get('added') and isinstance(tech['added'], list):
                        for t in tech['added']:
                            digest['tech_stack'].add(t if isinstance(t, str) else str(t))
                except (IOError, OSError, ValueError):
                    pass

        for p in digest['phases']:
            digest['phases'][p]['provides'] = list(digest['phases'][p]['provides'])
            digest['phases'][p]['affects'] = list(digest['phases'][p]['affects'])
            digest['phases'][p]['patterns'] = list(digest['phases'][p]['patterns'])
        digest['tech_stack'] = list(digest['tech_stack'])

        output(digest, raw)
    except Exception as e:
        error('Failed to generate history digest: %s' % str(e))


def cmd_resolve_model(cwd, agent_type, raw):
    if not agent_type:
        error('agent-type required')
    config = load_config(cwd)
    profile = config.get('model_profile', 'balanced')
    model = resolve_model_internal(cwd, agent_type)
    agent_models = MODEL_PROFILES.get(agent_type)
    result = {'model': model, 'profile': profile}
    if not agent_models:
        result['unknown_agent'] = True
    output(result, raw, model)


def cmd_commit(cwd, message, files, raw, amend=False):
    if not message and not amend:
        error('commit message required')
    config = load_config(cwd)

    if not config.get('commit_docs', True):
        output({'committed': False, 'hash': None, 'reason': 'skipped_commit_docs_false'}, raw, 'skipped')
        return

    if is_git_ignored(cwd, '.planning'):
        output({'committed': False, 'hash': None, 'reason': 'skipped_gitignored'}, raw, 'skipped')
        return

    files_to_stage = files if files else ['.planning/']
    for f in files_to_stage:
        exec_git(cwd, ['add', f])

    if amend:
        commit_args = ['commit', '--amend', '--no-edit']
    else:
        commit_args = ['commit', '-m', message]
    commit_result = exec_git(cwd, commit_args)

    if commit_result['exitCode'] != 0:
        if 'nothing to commit' in commit_result.get('stdout', '') or 'nothing to commit' in commit_result.get('stderr', ''):
            output({'committed': False, 'hash': None, 'reason': 'nothing_to_commit'}, raw, 'nothing')
            return
        output({'committed': False, 'hash': None, 'reason': 'nothing_to_commit', 'error': commit_result.get('stderr', '')}, raw, 'nothing')
        return

    hash_result = exec_git(cwd, ['rev-parse', '--short', 'HEAD'])
    h = hash_result['stdout'] if hash_result['exitCode'] == 0 else None
    output({'committed': True, 'hash': h, 'reason': 'committed'}, raw, h or 'committed')


def cmd_summary_extract(cwd, summary_path, fields, raw):
    if not summary_path:
        error('summary-path required for summary-extract')
    full_path = os.path.join(cwd, summary_path)
    if not os.path.exists(full_path):
        output({'error': 'File not found', 'path': summary_path}, raw)
        return

    with open(full_path, 'r', encoding='utf-8') as f:
        content = f.read()
    fm = extract_frontmatter(content)

    def parse_decisions(decisions_list):
        if not decisions_list or not isinstance(decisions_list, list):
            return []
        result = []
        for d in decisions_list:
            idx = d.find(':')
            if idx > 0:
                result.append({'summary': d[:idx].strip(), 'rationale': d[idx + 1:].strip()})
            else:
                result.append({'summary': d, 'rationale': None})
        return result

    tech = fm.get('tech-stack', {})
    full_result = {
        'path': summary_path,
        'one_liner': fm.get('one-liner', None),
        'key_files': fm.get('key-files', []),
        'tech_added': tech.get('added', []) if isinstance(tech, dict) else [],
        'patterns': fm.get('patterns-established', []),
        'decisions': parse_decisions(fm.get('key-decisions')),
        'requirements_completed': fm.get('requirements-completed', []),
    }

    if fields:
        filtered = {'path': summary_path}
        for field in fields:
            if field in full_result:
                filtered[field] = full_result[field]
        output(filtered, raw)
        return

    output(full_result, raw)


def cmd_websearch(query, options, raw):
    api_key = os.environ.get('BRAVE_API_KEY')

    if not api_key:
        output({'available': False, 'reason': 'BRAVE_API_KEY not set'}, raw, '')
        return

    if not query:
        output({'available': False, 'error': 'Query required'}, raw, '')
        return

    try:
        from urllib.request import Request, urlopen
        from urllib.parse import urlencode

        params = urlencode({
            'q': query,
            'count': str(options.get('limit', 10)),
            'country': 'us',
            'search_lang': 'en',
            'text_decorations': 'false',
        })
        freshness = options.get('freshness')
        if freshness:
            params += '&freshness=' + freshness

        url = 'https://api.search.brave.com/res/v1/web/search?' + params
        req = Request(url)
        req.add_header('Accept', 'application/json')
        req.add_header('X-Subscription-Token', api_key)

        resp = urlopen(req, timeout=15)
        data = json.loads(resp.read().decode('utf-8'))
        web_results = data.get('web', {}).get('results', [])
        results = [{
            'title': r.get('title', ''),
            'url': r.get('url', ''),
            'description': r.get('description', ''),
            'age': r.get('age', None),
        } for r in web_results]

        output({
            'available': True,
            'query': query,
            'count': len(results),
            'results': results,
        }, raw, '\n\n'.join('%s\n%s\n%s' % (r['title'], r['url'], r['description']) for r in results))
    except Exception as e:
        output({'available': False, 'error': str(e)}, raw, '')


def cmd_progress_render(cwd, fmt, raw):
    phases_dir = os.path.join(cwd, '.planning', 'phases')
    milestone = get_milestone_info(cwd)

    phases = []
    total_plans = 0
    total_summaries = 0

    try:
        entries = os.listdir(phases_dir)
        dirs = sorted(
            [e for e in entries if os.path.isdir(os.path.join(phases_dir, e))],
            key=_phase_sort_key
        )
        for d in dirs:
            dm = re.match(r'^(\d+(?:\.\d+)*)-?(.*)', d)
            phase_num = dm.group(1) if dm else d
            phase_name = dm.group(2).replace('-', ' ') if dm and dm.group(2) else ''
            phase_files = os.listdir(os.path.join(phases_dir, d))
            plans = len([f for f in phase_files if f.endswith('-PLAN.md') or f == 'PLAN.md'])
            summaries = len([f for f in phase_files if f.endswith('-SUMMARY.md') or f == 'SUMMARY.md'])
            total_plans += plans
            total_summaries += summaries

            if plans == 0:
                status = 'Pending'
            elif summaries >= plans:
                status = 'Complete'
            elif summaries > 0:
                status = 'In Progress'
            else:
                status = 'Planned'

            phases.append({'number': phase_num, 'name': phase_name, 'plans': plans, 'summaries': summaries, 'status': status})
    except (IOError, OSError):
        pass

    percent = min(100, round((total_summaries / total_plans) * 100)) if total_plans > 0 else 0

    if fmt == 'table':
        bar_width = 10
        filled = round((percent / 100) * bar_width)
        bar = '\u2588' * filled + '\u2591' * (bar_width - filled)
        out = '# %s %s\n\n' % (milestone['version'], milestone['name'])
        out += '**Progress:** [%s] %d/%d plans (%d%%)\n\n' % (bar, total_summaries, total_plans, percent)
        out += '| Phase | Name | Plans | Status |\n|-------|------|-------|--------|\n'
        for p in phases:
            out += '| %s | %s | %d/%d | %s |\n' % (p['number'], p['name'], p['summaries'], p['plans'], p['status'])
        output({'rendered': out}, raw, out)
    elif fmt == 'bar':
        bar_width = 20
        filled = round((percent / 100) * bar_width)
        bar = '\u2588' * filled + '\u2591' * (bar_width - filled)
        text = '[%s] %d/%d plans (%d%%)' % (bar, total_summaries, total_plans, percent)
        output({'bar': text, 'percent': percent, 'completed': total_summaries, 'total': total_plans}, raw, text)
    else:
        output({
            'milestone_version': milestone['version'],
            'milestone_name': milestone['name'],
            'phases': phases,
            'total_plans': total_plans,
            'total_summaries': total_summaries,
            'percent': percent,
        }, raw)


def cmd_todo_complete(cwd, filename, raw):
    if not filename:
        error('filename required for todo complete')
    pending_dir = os.path.join(cwd, '.planning', 'todos', 'pending')
    completed_dir = os.path.join(cwd, '.planning', 'todos', 'completed')
    source_path = os.path.join(pending_dir, filename)

    if not os.path.exists(source_path):
        error('Todo not found: %s' % filename)

    os.makedirs(completed_dir, exist_ok=True)
    with open(source_path, 'r', encoding='utf-8') as f:
        content = f.read()
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    content = 'completed: %s\n' % today + content

    with open(os.path.join(completed_dir, filename), 'w', encoding='utf-8') as f:
        f.write(content)
    os.unlink(source_path)
    output({'completed': True, 'file': filename, 'date': today}, raw, 'completed')


def cmd_scaffold(cwd, scaffold_type, options, raw):
    phase = options.get('phase')
    name = options.get('name')
    padded = normalize_phase_name(phase) if phase else '00'
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')

    phase_info = find_phase_internal(cwd, phase) if phase else None
    phase_dir = os.path.join(cwd, phase_info['directory']) if phase_info else None

    if phase and not phase_dir and scaffold_type != 'phase-dir':
        error('Phase %s directory not found' % phase)

    if scaffold_type == 'context':
        pname = name or (phase_info.get('phase_name') if phase_info else None) or 'Unnamed'
        file_path = os.path.join(phase_dir, '%s-CONTEXT.md' % padded)
        content = '---\nphase: "%s"\nname: "%s"\ncreated: %s\n---\n\n# Phase %s: %s \u2014 Context\n\n## Decisions\n\n_Decisions will be captured during /gsd:discuss-phase %s_\n\n## Discretion Areas\n\n_Areas where the executor can use judgment_\n\n## Deferred Ideas\n\n_Ideas to consider later_\n' % (padded, pname, today, phase, pname, phase)
    elif scaffold_type == 'uat':
        pname = name or (phase_info.get('phase_name') if phase_info else None) or 'Unnamed'
        file_path = os.path.join(phase_dir, '%s-UAT.md' % padded)
        content = '---\nphase: "%s"\nname: "%s"\ncreated: %s\nstatus: pending\n---\n\n# Phase %s: %s \u2014 User Acceptance Testing\n\n## Test Results\n\n| # | Test | Status | Notes |\n|---|------|--------|-------|\n\n## Summary\n\n_Pending UAT_\n' % (padded, pname, today, phase, pname)
    elif scaffold_type == 'verification':
        pname = name or (phase_info.get('phase_name') if phase_info else None) or 'Unnamed'
        file_path = os.path.join(phase_dir, '%s-VERIFICATION.md' % padded)
        content = '---\nphase: "%s"\nname: "%s"\ncreated: %s\nstatus: pending\n---\n\n# Phase %s: %s \u2014 Verification\n\n## Goal-Backward Verification\n\n**Phase Goal:** [From ROADMAP.md]\n\n## Checks\n\n| # | Requirement | Status | Evidence |\n|---|------------|--------|----------|\n\n## Result\n\n_Pending verification_\n' % (padded, pname, today, phase, pname)
    elif scaffold_type == 'phase-dir':
        if not phase or not name:
            error('phase and name required for phase-dir scaffold')
        slug = generate_slug_internal(name)
        dir_name = '%s-%s' % (padded, slug)
        phases_parent = os.path.join(cwd, '.planning', 'phases')
        os.makedirs(phases_parent, exist_ok=True)
        dir_path = os.path.join(phases_parent, dir_name)
        os.makedirs(dir_path, exist_ok=True)
        output({'created': True, 'directory': '.planning/phases/%s' % dir_name, 'path': dir_path}, raw, dir_path)
        return
    else:
        error('Unknown scaffold type: %s. Available: context, uat, verification, phase-dir' % scaffold_type)
        return

    if os.path.exists(file_path):
        output({'created': False, 'reason': 'already_exists', 'path': file_path}, raw, 'exists')
        return

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    rel_path = os.path.relpath(file_path, cwd)
    output({'created': True, 'path': rel_path}, raw, rel_path)
