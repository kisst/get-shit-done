"""Core — Shared utilities, constants, and internal helpers."""

import json
import os
import re
import subprocess
import sys
import tempfile
import time


def to_posix_path(p):
    """Normalize a path to always use forward slashes."""
    return p.replace(os.sep, '/')


# ─── Model Profile Table ─────────────────────────────────────────────────────

MODEL_PROFILES = {
    'gsd-planner':              {'quality': 'opus', 'balanced': 'opus',   'budget': 'sonnet'},
    'gsd-roadmapper':           {'quality': 'opus', 'balanced': 'sonnet', 'budget': 'sonnet'},
    'gsd-executor':             {'quality': 'opus', 'balanced': 'sonnet', 'budget': 'sonnet'},
    'gsd-phase-researcher':     {'quality': 'opus', 'balanced': 'sonnet', 'budget': 'haiku'},
    'gsd-project-researcher':   {'quality': 'opus', 'balanced': 'sonnet', 'budget': 'haiku'},
    'gsd-research-synthesizer': {'quality': 'sonnet', 'balanced': 'sonnet', 'budget': 'haiku'},
    'gsd-debugger':             {'quality': 'opus', 'balanced': 'sonnet', 'budget': 'sonnet'},
    'gsd-codebase-mapper':      {'quality': 'sonnet', 'balanced': 'haiku', 'budget': 'haiku'},
    'gsd-verifier':             {'quality': 'sonnet', 'balanced': 'sonnet', 'budget': 'haiku'},
    'gsd-plan-checker':         {'quality': 'sonnet', 'balanced': 'sonnet', 'budget': 'haiku'},
    'gsd-integration-checker':  {'quality': 'sonnet', 'balanced': 'sonnet', 'budget': 'haiku'},
}


# ─── Output helpers ───────────────────────────────────────────────────────────

def output(result, raw=False, raw_value=None):
    if raw and raw_value is not None:
        sys.stdout.write(str(raw_value))
    else:
        json_str = json.dumps(result, indent=2)
        if len(json_str) > 50000:
            tmp_path = os.path.join(tempfile.gettempdir(), 'gsd-%d.json' % int(time.time() * 1000))
            with open(tmp_path, 'w') as f:
                f.write(json_str)
            sys.stdout.write('@file:' + tmp_path)
        else:
            sys.stdout.write(json_str)
    sys.stdout.flush()
    sys.exit(0)


def error(message):
    sys.stderr.write('Error: ' + message + '\n')
    sys.exit(1)


# ─── File & Config utilities ──────────────────────────────────────────────────

def safe_read_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except (IOError, OSError):
        return None


def load_config(cwd):
    config_path = os.path.join(cwd, '.planning', 'config.json')
    defaults = {
        'model_profile': 'balanced',
        'commit_docs': True,
        'search_gitignored': False,
        'branching_strategy': 'none',
        'phase_branch_template': 'gsd/phase-{phase}-{slug}',
        'milestone_branch_template': 'gsd/{milestone}-{slug}',
        'research': True,
        'plan_checker': True,
        'verifier': True,
        'nyquist_validation': False,
        'parallelization': True,
        'brave_search': False,
    }

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            parsed = json.load(f)
    except (IOError, OSError, ValueError):
        return defaults

    def get(key, nested=None):
        if key in parsed:
            return parsed[key]
        if nested and nested['section'] in parsed:
            section = parsed[nested['section']]
            if isinstance(section, dict) and nested['field'] in section:
                return section[nested['field']]
        return None

    par_val = get('parallelization')
    if isinstance(par_val, bool):
        parallelization = par_val
    elif isinstance(par_val, dict) and 'enabled' in par_val:
        parallelization = par_val['enabled']
    else:
        parallelization = defaults['parallelization']

    def _or(val, default):
        return val if val is not None else default

    return {
        'model_profile': _or(get('model_profile'), defaults['model_profile']),
        'commit_docs': _or(get('commit_docs', {'section': 'planning', 'field': 'commit_docs'}), defaults['commit_docs']),
        'search_gitignored': _or(get('search_gitignored', {'section': 'planning', 'field': 'search_gitignored'}), defaults['search_gitignored']),
        'branching_strategy': _or(get('branching_strategy', {'section': 'git', 'field': 'branching_strategy'}), defaults['branching_strategy']),
        'phase_branch_template': _or(get('phase_branch_template', {'section': 'git', 'field': 'phase_branch_template'}), defaults['phase_branch_template']),
        'milestone_branch_template': _or(get('milestone_branch_template', {'section': 'git', 'field': 'milestone_branch_template'}), defaults['milestone_branch_template']),
        'research': _or(get('research', {'section': 'workflow', 'field': 'research'}), defaults['research']),
        'plan_checker': _or(get('plan_checker', {'section': 'workflow', 'field': 'plan_check'}), defaults['plan_checker']),
        'verifier': _or(get('verifier', {'section': 'workflow', 'field': 'verifier'}), defaults['verifier']),
        'nyquist_validation': _or(get('nyquist_validation', {'section': 'workflow', 'field': 'nyquist_validation'}), defaults['nyquist_validation']),
        'parallelization': parallelization,
        'brave_search': _or(get('brave_search'), defaults['brave_search']),
        'model_overrides': parsed.get('model_overrides', None),
    }


# ─── Git utilities ────────────────────────────────────────────────────────────

def is_git_ignored(cwd, target_path):
    safe = re.sub(r'[^a-zA-Z0-9._\-/]', '', target_path)
    try:
        subprocess.check_output(
            ['git', 'check-ignore', '-q', '--', safe],
            cwd=cwd, stderr=subprocess.PIPE
        )
        return True
    except subprocess.CalledProcessError:
        return False


def exec_git(cwd, args):
    try:
        escaped = []
        for a in args:
            if re.match(r'^[a-zA-Z0-9._\-/=:@]+$', a):
                escaped.append(a)
            else:
                escaped.append("'" + a.replace("'", "'\\''") + "'")
        result = subprocess.run(
            'git ' + ' '.join(escaped),
            cwd=cwd, shell=True, capture_output=True, text=True
        )
        return {
            'exitCode': result.returncode,
            'stdout': result.stdout.strip(),
            'stderr': result.stderr.strip(),
        }
    except Exception:
        return {'exitCode': 1, 'stdout': '', 'stderr': ''}


# ─── Phase utilities ──────────────────────────────────────────────────────────

def escape_regex(value):
    return re.escape(str(value))


def normalize_phase_name(phase):
    m = re.match(r'^(\d+)([A-Z])?((?:\.\d+)*)', str(phase), re.IGNORECASE)
    if not m:
        return str(phase)
    padded = m.group(1).zfill(2)
    letter = m.group(2).upper() if m.group(2) else ''
    decimal = m.group(3) or ''
    return padded + letter + decimal


def compare_phase_num(a, b):
    pa = re.match(r'^(\d+)([A-Z])?((?:\.\d+)*)', str(a), re.IGNORECASE)
    pb = re.match(r'^(\d+)([A-Z])?((?:\.\d+)*)', str(b), re.IGNORECASE)
    if not pa or not pb:
        sa, sb = str(a), str(b)
        return -1 if sa < sb else (1 if sa > sb else 0)

    int_diff = int(pa.group(1)) - int(pb.group(1))
    if int_diff != 0:
        return int_diff

    la = (pa.group(2) or '').upper()
    lb = (pb.group(2) or '').upper()
    if la != lb:
        if not la:
            return -1
        if not lb:
            return 1
        return -1 if la < lb else 1

    a_dec = [int(x) for x in pa.group(3)[1:].split('.')] if pa.group(3) else []
    b_dec = [int(x) for x in pb.group(3)[1:].split('.')] if pb.group(3) else []
    max_len = max(len(a_dec), len(b_dec))
    if len(a_dec) == 0 and len(b_dec) > 0:
        return -1
    if len(b_dec) == 0 and len(a_dec) > 0:
        return 1
    for i in range(max_len):
        av = a_dec[i] if i < len(a_dec) else 0
        bv = b_dec[i] if i < len(b_dec) else 0
        if av != bv:
            return av - bv
    return 0


def _phase_sort_key(name):
    """Sort key for phase directory names using compare_phase_num."""
    return _PhaseKey(name)


class _PhaseKey:
    def __init__(self, name):
        self.name = name

    def __lt__(self, other):
        return compare_phase_num(self.name, other.name) < 0

    def __le__(self, other):
        return compare_phase_num(self.name, other.name) <= 0

    def __gt__(self, other):
        return compare_phase_num(self.name, other.name) > 0

    def __ge__(self, other):
        return compare_phase_num(self.name, other.name) >= 0

    def __eq__(self, other):
        return compare_phase_num(self.name, other.name) == 0


def search_phase_in_dir(base_dir, rel_base, normalized):
    try:
        entries = os.listdir(base_dir)
        dirs = sorted(
            [e for e in entries if os.path.isdir(os.path.join(base_dir, e))],
            key=_phase_sort_key
        )
        match = None
        for d in dirs:
            if d.startswith(normalized):
                match = d
                break
        if not match:
            return None

        dir_match = re.match(r'^(\d+[A-Z]?(?:\.\d+)*)-?(.*)', match, re.IGNORECASE)
        phase_number = dir_match.group(1) if dir_match else normalized
        phase_name = dir_match.group(2) if dir_match and dir_match.group(2) else None
        phase_dir = os.path.join(base_dir, match)
        phase_files = os.listdir(phase_dir)

        plans = sorted([f for f in phase_files if f.endswith('-PLAN.md') or f == 'PLAN.md'])
        summaries = sorted([f for f in phase_files if f.endswith('-SUMMARY.md') or f == 'SUMMARY.md'])
        has_research = any(f.endswith('-RESEARCH.md') or f == 'RESEARCH.md' for f in phase_files)
        has_context = any(f.endswith('-CONTEXT.md') or f == 'CONTEXT.md' for f in phase_files)
        has_verification = any(f.endswith('-VERIFICATION.md') or f == 'VERIFICATION.md' for f in phase_files)

        completed_plan_ids = set()
        for s in summaries:
            completed_plan_ids.add(s.replace('-SUMMARY.md', '').replace('SUMMARY.md', ''))
        incomplete_plans = []
        for p in plans:
            plan_id = p.replace('-PLAN.md', '').replace('PLAN.md', '')
            if plan_id not in completed_plan_ids:
                incomplete_plans.append(p)

        slug = None
        if phase_name:
            slug = re.sub(r'[^a-z0-9]+', '-', phase_name.lower()).strip('-')

        return {
            'found': True,
            'directory': to_posix_path(os.path.join(rel_base, match)),
            'phase_number': phase_number,
            'phase_name': phase_name,
            'phase_slug': slug,
            'plans': plans,
            'summaries': summaries,
            'incomplete_plans': incomplete_plans,
            'has_research': has_research,
            'has_context': has_context,
            'has_verification': has_verification,
        }
    except (IOError, OSError):
        return None


def find_phase_internal(cwd, phase):
    if not phase:
        return None

    phases_dir = os.path.join(cwd, '.planning', 'phases')
    normalized = normalize_phase_name(phase)

    current = search_phase_in_dir(phases_dir, '.planning/phases', normalized)
    if current:
        return current

    milestones_dir = os.path.join(cwd, '.planning', 'milestones')
    if not os.path.exists(milestones_dir):
        return None

    try:
        milestone_entries = os.listdir(milestones_dir)
        archive_dirs = sorted(
            [e for e in milestone_entries
             if os.path.isdir(os.path.join(milestones_dir, e)) and re.match(r'^v[\d.]+-phases$', e)],
            reverse=True
        )
        for archive_name in archive_dirs:
            version = re.match(r'^(v[\d.]+)-phases$', archive_name).group(1)
            archive_path = os.path.join(milestones_dir, archive_name)
            rel_base = '.planning/milestones/' + archive_name
            result = search_phase_in_dir(archive_path, rel_base, normalized)
            if result:
                result['archived'] = version
                return result
    except (IOError, OSError):
        pass

    return None


def get_archived_phase_dirs(cwd):
    milestones_dir = os.path.join(cwd, '.planning', 'milestones')
    results = []

    if not os.path.exists(milestones_dir):
        return results

    try:
        milestone_entries = os.listdir(milestones_dir)
        phase_dirs = sorted(
            [e for e in milestone_entries
             if os.path.isdir(os.path.join(milestones_dir, e)) and re.match(r'^v[\d.]+-phases$', e)],
            reverse=True
        )
        for archive_name in phase_dirs:
            version = re.match(r'^(v[\d.]+)-phases$', archive_name).group(1)
            archive_path = os.path.join(milestones_dir, archive_name)
            entries = os.listdir(archive_path)
            dirs = sorted(
                [e for e in entries if os.path.isdir(os.path.join(archive_path, e))],
                key=_phase_sort_key
            )
            for d in dirs:
                results.append({
                    'name': d,
                    'milestone': version,
                    'basePath': os.path.join('.planning', 'milestones', archive_name),
                    'fullPath': os.path.join(archive_path, d),
                })
    except (IOError, OSError):
        pass

    return results


# ─── Roadmap & model utilities ────────────────────────────────────────────────

def get_roadmap_phase_internal(cwd, phase_num):
    if not phase_num:
        return None
    roadmap_path = os.path.join(cwd, '.planning', 'ROADMAP.md')
    if not os.path.exists(roadmap_path):
        return None

    try:
        with open(roadmap_path, 'r', encoding='utf-8') as f:
            content = f.read()
        escaped_phase = escape_regex(str(phase_num))
        pattern = r'#{2,4}\s*Phase\s+' + escaped_phase + r':\s*([^\n]+)'
        header_match = re.search(pattern, content, re.IGNORECASE)
        if not header_match:
            return None

        phase_name = header_match.group(1).strip()
        header_index = header_match.start()
        rest = content[header_index:]
        next_match = re.search(r'\n#{2,4}\s+Phase\s+\d', rest, re.IGNORECASE)
        section_end = header_index + next_match.start() if next_match else len(content)
        section = content[header_index:section_end].strip()

        goal_match = re.search(r'\*\*Goal:\*\*\s*([^\n]+)', section, re.IGNORECASE)
        goal = goal_match.group(1).strip() if goal_match else None

        return {
            'found': True,
            'phase_number': str(phase_num),
            'phase_name': phase_name,
            'goal': goal,
            'section': section,
        }
    except (IOError, OSError):
        return None


def resolve_model_internal(cwd, agent_type):
    config = load_config(cwd)

    overrides = config.get('model_overrides')
    if overrides and isinstance(overrides, dict):
        override = overrides.get(agent_type)
        if override:
            return 'inherit' if override == 'opus' else override

    profile = config.get('model_profile', 'balanced')
    agent_models = MODEL_PROFILES.get(agent_type)
    if not agent_models:
        return 'sonnet'
    resolved = agent_models.get(profile, agent_models.get('balanced', 'sonnet'))
    return 'inherit' if resolved == 'opus' else resolved


# ─── Misc utilities ───────────────────────────────────────────────────────────

def path_exists_internal(cwd, target_path):
    full_path = target_path if os.path.isabs(target_path) else os.path.join(cwd, target_path)
    return os.path.exists(full_path)


def generate_slug_internal(text):
    if not text:
        return None
    return re.sub(r'^-+|-+$', '', re.sub(r'[^a-z0-9]+', '-', text.lower()))


def get_milestone_info(cwd):
    try:
        with open(os.path.join(cwd, '.planning', 'ROADMAP.md'), 'r', encoding='utf-8') as f:
            roadmap = f.read()
        cleaned = re.sub(r'<details>[\s\S]*?</details>', '', roadmap, flags=re.IGNORECASE)
        heading_match = re.search(r'## .*v(\d+\.\d+)[:\s]+([^\n(]+)', cleaned)
        if heading_match:
            return {
                'version': 'v' + heading_match.group(1),
                'name': heading_match.group(2).strip(),
            }
        version_match = re.search(r'v(\d+\.\d+)', cleaned)
        return {
            'version': version_match.group(0) if version_match else 'v1.0',
            'name': 'milestone',
        }
    except (IOError, OSError):
        return {'version': 'v1.0', 'name': 'milestone'}
