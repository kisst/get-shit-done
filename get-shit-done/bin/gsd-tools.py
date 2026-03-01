#!/usr/bin/env python3
"""GSD Tools — CLI utility for GSD workflow operations.

Replaces repetitive inline bash patterns across ~50 GSD command/workflow/agent files.
Centralizes: config parsing, model resolution, phase lookup, git commits, summary verification.

Usage: python3 gsd-tools.py <command> [args] [--raw] [--cwd <path>]
"""

import json
import os
import sys

from lib_py.core import error
from lib_py import state
from lib_py import phase
from lib_py import roadmap
from lib_py import verify
from lib_py import config
from lib_py import template
from lib_py import milestone
from lib_py import commands
from lib_py import init
from lib_py import frontmatter


def _find_arg(args, flag):
    """Return the value after --flag, or None if not present."""
    try:
        idx = args.index(flag)
        if idx + 1 < len(args) and not args[idx + 1].startswith('--'):
            return args[idx + 1]
    except ValueError:
        pass
    return None


def main():
    args = list(sys.argv[1:])

    # Optional cwd override for sandboxed subagents running outside project root.
    cwd = os.getcwd()
    cwd_eq_arg = None
    for a in args:
        if a.startswith('--cwd='):
            cwd_eq_arg = a
            break

    if cwd_eq_arg:
        value = cwd_eq_arg[len('--cwd='):].strip()
        if not value:
            error('Missing value for --cwd')
        args.remove(cwd_eq_arg)
        cwd = os.path.abspath(value)
    elif '--cwd' in args:
        cwd_idx = args.index('--cwd')
        if cwd_idx + 1 >= len(args) or args[cwd_idx + 1].startswith('--'):
            error('Missing value for --cwd')
        value = args[cwd_idx + 1]
        del args[cwd_idx:cwd_idx + 2]
        cwd = os.path.abspath(value)

    if not os.path.isdir(cwd):
        error('Invalid --cwd: %s' % cwd)

    raw = False
    if '--raw' in args:
        raw = True
        args.remove('--raw')

    command = args[0] if args else None

    if not command:
        error(
            'Usage: gsd-tools <command> [args] [--raw] [--cwd <path>]\n'
            'Commands: state, resolve-model, find-phase, commit, verify-summary, '
            'verify, frontmatter, template, generate-slug, current-timestamp, '
            'list-todos, verify-path-exists, config-ensure-section, init'
        )

    if command == 'state':
        sub = args[1] if len(args) > 1 else None
        if sub == 'json':
            state.cmd_state_json(cwd, raw)
        elif sub == 'update':
            state.cmd_state_update(cwd, args[2] if len(args) > 2 else None, args[3] if len(args) > 3 else None)
        elif sub == 'get':
            state.cmd_state_get(cwd, args[2] if len(args) > 2 else None, raw)
        elif sub == 'patch':
            patches = {}
            i = 2
            while i < len(args) - 1:
                key = args[i].lstrip('-')
                val = args[i + 1]
                if key and val is not None:
                    patches[key] = val
                i += 2
            state.cmd_state_patch(cwd, patches, raw)
        elif sub == 'advance-plan':
            state.cmd_state_advance_plan(cwd, raw)
        elif sub == 'record-metric':
            state.cmd_state_record_metric(cwd, {
                'phase': _find_arg(args, '--phase'),
                'plan': _find_arg(args, '--plan'),
                'duration': _find_arg(args, '--duration'),
                'tasks': _find_arg(args, '--tasks'),
                'files': _find_arg(args, '--files'),
            }, raw)
        elif sub == 'update-progress':
            state.cmd_state_update_progress(cwd, raw)
        elif sub == 'add-decision':
            state.cmd_state_add_decision(cwd, {
                'phase': _find_arg(args, '--phase'),
                'summary': _find_arg(args, '--summary'),
                'summary_file': _find_arg(args, '--summary-file'),
                'rationale': _find_arg(args, '--rationale') or '',
                'rationale_file': _find_arg(args, '--rationale-file'),
            }, raw)
        elif sub == 'add-blocker':
            state.cmd_state_add_blocker(cwd, {
                'text': _find_arg(args, '--text'),
                'text_file': _find_arg(args, '--text-file'),
            }, raw)
        elif sub == 'resolve-blocker':
            state.cmd_state_resolve_blocker(cwd, _find_arg(args, '--text'), raw)
        elif sub == 'record-session':
            state.cmd_state_record_session(cwd, {
                'stopped_at': _find_arg(args, '--stopped-at'),
                'resume_file': _find_arg(args, '--resume-file') or 'None',
            }, raw)
        else:
            state.cmd_state_load(cwd, raw)

    elif command == 'resolve-model':
        commands.cmd_resolve_model(cwd, args[1] if len(args) > 1 else None, raw)

    elif command == 'find-phase':
        phase.cmd_find_phase(cwd, args[1] if len(args) > 1 else None, raw)

    elif command == 'commit':
        amend = '--amend' in args
        message = args[1] if len(args) > 1 else None
        files_index = args.index('--files') if '--files' in args else -1
        files = [a for a in args[files_index + 1:] if not a.startswith('--')] if files_index != -1 else []
        commands.cmd_commit(cwd, message, files, raw, amend)

    elif command == 'verify-summary':
        summary_path = args[1] if len(args) > 1 else None
        count_val = _find_arg(args, '--check-count')
        check_count = int(count_val) if count_val else 2
        verify.cmd_verify_summary(cwd, summary_path, check_count, raw)

    elif command == 'template':
        sub = args[1] if len(args) > 1 else None
        if sub == 'select':
            template.cmd_template_select(cwd, args[2] if len(args) > 2 else None, raw)
        elif sub == 'fill':
            template_type = args[2] if len(args) > 2 else None
            fields_val = _find_arg(args, '--fields')
            template.cmd_template_fill(cwd, template_type, {
                'phase': _find_arg(args, '--phase'),
                'plan': _find_arg(args, '--plan'),
                'name': _find_arg(args, '--name'),
                'type': _find_arg(args, '--type') or 'execute',
                'wave': _find_arg(args, '--wave') or '1',
                'fields': json.loads(fields_val) if fields_val else {},
            }, raw)
        else:
            error('Unknown template subcommand. Available: select, fill')

    elif command == 'frontmatter':
        sub = args[1] if len(args) > 1 else None
        file_arg = args[2] if len(args) > 2 else None
        if sub == 'get':
            frontmatter.cmd_frontmatter_get(cwd, file_arg, _find_arg(args, '--field'), raw)
        elif sub == 'set':
            frontmatter.cmd_frontmatter_set(cwd, file_arg, _find_arg(args, '--field'), _find_arg(args, '--value'), raw)
        elif sub == 'merge':
            frontmatter.cmd_frontmatter_merge(cwd, file_arg, _find_arg(args, '--data'), raw)
        elif sub == 'validate':
            frontmatter.cmd_frontmatter_validate(cwd, file_arg, _find_arg(args, '--schema'), raw)
        else:
            error('Unknown frontmatter subcommand. Available: get, set, merge, validate')

    elif command == 'verify':
        sub = args[1] if len(args) > 1 else None
        if sub == 'plan-structure':
            verify.cmd_verify_plan_structure(cwd, args[2] if len(args) > 2 else None, raw)
        elif sub == 'phase-completeness':
            verify.cmd_verify_phase_completeness(cwd, args[2] if len(args) > 2 else None, raw)
        elif sub == 'references':
            verify.cmd_verify_references(cwd, args[2] if len(args) > 2 else None, raw)
        elif sub == 'commits':
            verify.cmd_verify_commits(cwd, args[2:], raw)
        elif sub == 'artifacts':
            verify.cmd_verify_artifacts(cwd, args[2] if len(args) > 2 else None, raw)
        elif sub == 'key-links':
            verify.cmd_verify_key_links(cwd, args[2] if len(args) > 2 else None, raw)
        else:
            error('Unknown verify subcommand. Available: plan-structure, phase-completeness, references, commits, artifacts, key-links')

    elif command == 'generate-slug':
        commands.cmd_generate_slug(args[1] if len(args) > 1 else None, raw)

    elif command == 'current-timestamp':
        commands.cmd_current_timestamp(args[1] if len(args) > 1 else 'full', raw)

    elif command == 'list-todos':
        commands.cmd_list_todos(cwd, args[1] if len(args) > 1 else None, raw)

    elif command == 'verify-path-exists':
        commands.cmd_verify_path_exists(cwd, args[1] if len(args) > 1 else None, raw)

    elif command == 'config-ensure-section':
        config.cmd_config_ensure_section(cwd, raw)

    elif command == 'config-set':
        config.cmd_config_set(cwd, args[1] if len(args) > 1 else None, args[2] if len(args) > 2 else None, raw)

    elif command == 'config-get':
        config.cmd_config_get(cwd, args[1] if len(args) > 1 else None, raw)

    elif command == 'history-digest':
        commands.cmd_history_digest(cwd, raw)

    elif command == 'phases':
        sub = args[1] if len(args) > 1 else None
        if sub == 'list':
            options = {
                'type': _find_arg(args, '--type'),
                'phase': _find_arg(args, '--phase'),
                'includeArchived': '--include-archived' in args,
            }
            phase.cmd_phases_list(cwd, options, raw)
        else:
            error('Unknown phases subcommand. Available: list')

    elif command == 'roadmap':
        sub = args[1] if len(args) > 1 else None
        if sub == 'get-phase':
            roadmap.cmd_roadmap_get_phase(cwd, args[2] if len(args) > 2 else None, raw)
        elif sub == 'analyze':
            roadmap.cmd_roadmap_analyze(cwd, raw)
        elif sub == 'update-plan-progress':
            roadmap.cmd_roadmap_update_plan_progress(cwd, args[2] if len(args) > 2 else None, raw)
        else:
            error('Unknown roadmap subcommand. Available: get-phase, analyze, update-plan-progress')

    elif command == 'requirements':
        sub = args[1] if len(args) > 1 else None
        if sub == 'mark-complete':
            milestone.cmd_requirements_mark_complete(cwd, args[2:], raw)
        else:
            error('Unknown requirements subcommand. Available: mark-complete')

    elif command == 'phase':
        sub = args[1] if len(args) > 1 else None
        if sub == 'next-decimal':
            phase.cmd_phase_next_decimal(cwd, args[2] if len(args) > 2 else None, raw)
        elif sub == 'add':
            phase.cmd_phase_add(cwd, ' '.join(args[2:]), raw)
        elif sub == 'insert':
            phase.cmd_phase_insert(cwd, args[2] if len(args) > 2 else None, ' '.join(args[3:]), raw)
        elif sub == 'remove':
            force_flag = '--force' in args
            phase.cmd_phase_remove(cwd, args[2] if len(args) > 2 else None, {'force': force_flag}, raw)
        elif sub == 'complete':
            phase.cmd_phase_complete(cwd, args[2] if len(args) > 2 else None, raw)
        else:
            error('Unknown phase subcommand. Available: next-decimal, add, insert, remove, complete')

    elif command == 'milestone':
        sub = args[1] if len(args) > 1 else None
        if sub == 'complete':
            name_idx = args.index('--name') if '--name' in args else -1
            archive_phases = '--archive-phases' in args
            milestone_name = None
            if name_idx != -1:
                name_args = []
                for i in range(name_idx + 1, len(args)):
                    if args[i].startswith('--'):
                        break
                    name_args.append(args[i])
                milestone_name = ' '.join(name_args) or None
            milestone.cmd_milestone_complete(cwd, args[2] if len(args) > 2 else None, {'name': milestone_name, 'archivePhases': archive_phases}, raw)
        else:
            error('Unknown milestone subcommand. Available: complete')

    elif command == 'validate':
        sub = args[1] if len(args) > 1 else None
        if sub == 'consistency':
            verify.cmd_validate_consistency(cwd, raw)
        elif sub == 'health':
            repair_flag = '--repair' in args
            verify.cmd_validate_health(cwd, {'repair': repair_flag}, raw)
        else:
            error('Unknown validate subcommand. Available: consistency, health')

    elif command == 'progress':
        sub = args[1] if len(args) > 1 else 'json'
        commands.cmd_progress_render(cwd, sub, raw)

    elif command == 'todo':
        sub = args[1] if len(args) > 1 else None
        if sub == 'complete':
            commands.cmd_todo_complete(cwd, args[2] if len(args) > 2 else None, raw)
        else:
            error('Unknown todo subcommand. Available: complete')

    elif command == 'scaffold':
        scaffold_type = args[1] if len(args) > 1 else None
        name_val = _find_arg(args, '--name')
        if name_val:
            name_idx = args.index('--name')
            name_val = ' '.join(args[name_idx + 1:])
        commands.cmd_scaffold(cwd, scaffold_type, {
            'phase': _find_arg(args, '--phase'),
            'name': name_val,
        }, raw)

    elif command == 'init':
        workflow = args[1] if len(args) > 1 else None
        if workflow == 'execute-phase':
            init.cmd_init_execute_phase(cwd, args[2] if len(args) > 2 else None, raw)
        elif workflow == 'plan-phase':
            init.cmd_init_plan_phase(cwd, args[2] if len(args) > 2 else None, raw)
        elif workflow == 'new-project':
            init.cmd_init_new_project(cwd, raw)
        elif workflow == 'new-milestone':
            init.cmd_init_new_milestone(cwd, raw)
        elif workflow == 'quick':
            init.cmd_init_quick(cwd, ' '.join(args[2:]), raw)
        elif workflow == 'resume':
            init.cmd_init_resume(cwd, raw)
        elif workflow == 'verify-work':
            init.cmd_init_verify_work(cwd, args[2] if len(args) > 2 else None, raw)
        elif workflow == 'phase-op':
            init.cmd_init_phase_op(cwd, args[2] if len(args) > 2 else None, raw)
        elif workflow == 'todos':
            init.cmd_init_todos(cwd, args[2] if len(args) > 2 else None, raw)
        elif workflow == 'milestone-op':
            init.cmd_init_milestone_op(cwd, raw)
        elif workflow == 'map-codebase':
            init.cmd_init_map_codebase(cwd, raw)
        elif workflow == 'progress':
            init.cmd_init_progress(cwd, raw)
        else:
            error(
                'Unknown init workflow: %s\n'
                'Available: execute-phase, plan-phase, new-project, new-milestone, '
                'quick, resume, verify-work, phase-op, todos, milestone-op, '
                'map-codebase, progress' % workflow
            )

    elif command == 'phase-plan-index':
        phase.cmd_phase_plan_index(cwd, args[1] if len(args) > 1 else None, raw)

    elif command == 'state-snapshot':
        state.cmd_state_snapshot(cwd, raw)

    elif command == 'summary-extract':
        summary_path = args[1] if len(args) > 1 else None
        fields_val = _find_arg(args, '--fields')
        fields = fields_val.split(',') if fields_val else None
        commands.cmd_summary_extract(cwd, summary_path, fields, raw)

    elif command == 'websearch':
        query = args[1] if len(args) > 1 else None
        limit_val = _find_arg(args, '--limit')
        commands.cmd_websearch(query, {
            'limit': int(limit_val) if limit_val else 10,
            'freshness': _find_arg(args, '--freshness'),
        }, raw)

    else:
        error('Unknown command: %s' % command)


if __name__ == '__main__':
    main()
