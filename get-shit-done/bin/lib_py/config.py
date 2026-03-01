"""Config — Configuration CRUD commands."""

import json
import os

from .core import output, error


def cmd_config_ensure_section(cwd, raw):
    config_path = os.path.join(cwd, '.planning', 'config.json')
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                existing = json.load(f)
            output({'exists': True, 'config': existing}, raw)
            return
        except (ValueError, IOError):
            pass

    planning_dir = os.path.join(cwd, '.planning')
    if not os.path.exists(planning_dir):
        os.makedirs(planning_dir, exist_ok=True)

    default_config = {
        'model_profile': 'balanced',
        'workflow': {
            'research': True,
            'plan_check': True,
            'verifier': True,
            'nyquist_validation': False,
        },
        'planning': {
            'commit_docs': True,
            'search_gitignored': False,
        },
        'git': {
            'branching_strategy': 'none',
            'phase_branch_template': 'gsd/phase-{phase}-{slug}',
            'milestone_branch_template': 'gsd/{milestone}-{slug}',
        },
        'parallelization': True,
        'brave_search': False,
    }

    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(default_config, f, indent=2)
    output({'created': True, 'config': default_config}, raw)


def cmd_config_set(cwd, key, value, raw):
    if not key or value is None:
        error('key and value required')
    config_path = os.path.join(cwd, '.planning', 'config.json')
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except (IOError, ValueError):
        config = {}

    try:
        parsed_value = json.loads(value)
    except (ValueError, TypeError):
        parsed_value = value

    parts = key.split('.')
    target = config
    for part in parts[:-1]:
        if part not in target or not isinstance(target[part], dict):
            target[part] = {}
        target = target[part]
    target[parts[-1]] = parsed_value

    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2)
    output({'updated': True, 'key': key, 'value': parsed_value}, raw, 'true')


def cmd_config_get(cwd, key, raw):
    if not key:
        error('key required')
    config_path = os.path.join(cwd, '.planning', 'config.json')
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except (IOError, ValueError):
        config = {}

    parts = key.split('.')
    target = config
    for part in parts:
        if isinstance(target, dict) and part in target:
            target = target[part]
        else:
            output({'error': 'Key not found', 'key': key}, raw)
            return
    output({'key': key, 'value': target}, raw, json.dumps(target) if not isinstance(target, str) else target)
