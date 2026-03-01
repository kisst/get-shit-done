"""Frontmatter — YAML frontmatter parsing, serialization, and CRUD commands."""

import json
import os
import re

from .core import safe_read_file, output, error


# ─── Parsing engine ───────────────────────────────────────────────────────────

def extract_frontmatter(content):
    frontmatter = {}
    match = re.match(r'^---\n([\s\S]+?)\n---', content)
    if not match:
        return frontmatter

    yaml = match.group(1)
    lines = yaml.split('\n')

    stack = [{'obj': frontmatter, 'key': None, 'indent': -1}]

    for line in lines:
        if line.strip() == '':
            continue

        indent_match = re.match(r'^(\s*)', line)
        indent = len(indent_match.group(1)) if indent_match else 0

        while len(stack) > 1 and indent <= stack[-1]['indent']:
            stack.pop()

        current = stack[-1]

        key_match = re.match(r'^(\s*)([a-zA-Z0-9_-]+):\s*(.*)', line)
        if key_match:
            key = key_match.group(2)
            value = key_match.group(3).strip()

            if value == '' or value == '[':
                current['obj'][key] = [] if value == '[' else {}
                current['key'] = None
                stack.append({'obj': current['obj'][key], 'key': None, 'indent': indent})
            elif value.startswith('[') and value.endswith(']'):
                items = [s.strip().strip('"').strip("'") for s in value[1:-1].split(',')]
                current['obj'][key] = [x for x in items if x]
                current['key'] = None
            else:
                current['obj'][key] = value.strip('"').strip("'")
                current['key'] = None
        elif line.strip().startswith('- '):
            item_value = line.strip()[2:].strip('"').strip("'")

            if isinstance(current['obj'], dict) and len(current['obj']) == 0:
                parent = stack[-2] if len(stack) > 1 else None
                if parent:
                    for k in list(parent['obj'].keys()):
                        if parent['obj'][k] is current['obj']:
                            parent['obj'][k] = [item_value]
                            current['obj'] = parent['obj'][k]
                            break
            elif isinstance(current['obj'], list):
                current['obj'].append(item_value)


    return frontmatter


def reconstruct_frontmatter(obj):
    lines = []
    for key, value in obj.items():
        if value is None:
            continue
        if isinstance(value, list):
            if len(value) == 0:
                lines.append('%s: []' % key)
            elif (all(isinstance(v, str) for v in value)
                  and len(value) <= 3
                  and len(', '.join(value)) < 60):
                lines.append('%s: [%s]' % (key, ', '.join(value)))
            else:
                lines.append('%s:' % key)
                for item in value:
                    s = str(item)
                    if ':' in s or '#' in s:
                        lines.append('  - "%s"' % s)
                    else:
                        lines.append('  - %s' % s)
        elif isinstance(value, dict):
            lines.append('%s:' % key)
            for subkey, subval in value.items():
                if subval is None:
                    continue
                if isinstance(subval, list):
                    if len(subval) == 0:
                        lines.append('  %s: []' % subkey)
                    elif (all(isinstance(v, str) for v in subval)
                          and len(subval) <= 3
                          and len(', '.join(subval)) < 60):
                        lines.append('  %s: [%s]' % (subkey, ', '.join(subval)))
                    else:
                        lines.append('  %s:' % subkey)
                        for item in subval:
                            s = str(item)
                            if ':' in s or '#' in s:
                                lines.append('    - "%s"' % s)
                            else:
                                lines.append('    - %s' % s)
                elif isinstance(subval, dict):
                    lines.append('  %s:' % subkey)
                    for subsubkey, subsubval in subval.items():
                        if subsubval is None:
                            continue
                        if isinstance(subsubval, list):
                            if len(subsubval) == 0:
                                lines.append('    %s: []' % subsubkey)
                            else:
                                lines.append('    %s:' % subsubkey)
                                for item in subsubval:
                                    lines.append('      - %s' % item)
                        else:
                            lines.append('    %s: %s' % (subsubkey, subsubval))
                else:
                    sv = str(subval)
                    if ':' in sv or '#' in sv:
                        lines.append('  %s: "%s"' % (subkey, sv))
                    else:
                        lines.append('  %s: %s' % (subkey, sv))
        else:
            sv = str(value)
            if ':' in sv or '#' in sv or sv.startswith('[') or sv.startswith('{'):
                lines.append('%s: "%s"' % (key, sv))
            else:
                lines.append('%s: %s' % (key, sv))
    return '\n'.join(lines)


def splice_frontmatter(content, new_obj):
    yaml_str = reconstruct_frontmatter(new_obj)
    match = re.match(r'^---\n[\s\S]+?\n---', content)
    if match:
        return '---\n%s\n---' % yaml_str + content[match.end():]
    return '---\n%s\n---\n\n' % yaml_str + content


def parse_must_haves_block(content, block_name):
    fm_match = re.match(r'^---\n([\s\S]+?)\n---', content)
    if not fm_match:
        return []

    yaml = fm_match.group(1)
    block_pattern = re.compile(r'^\s{4}%s:\s*$' % re.escape(block_name), re.MULTILINE)
    block_start_match = block_pattern.search(yaml)
    if not block_start_match:
        return []

    after_block = yaml[block_start_match.start():]
    block_lines = after_block.split('\n')[1:]

    items = []
    current = None

    for line in block_lines:
        if line.strip() == '':
            continue
        indent_match = re.match(r'^(\s*)', line)
        indent = len(indent_match.group(1))
        if indent <= 4 and line.strip() != '':
            break

        if re.match(r'^\s{6}-\s+', line):
            if current is not None:
                items.append(current)
            current = {}
            simple_match = re.match(r'^\s{6}-\s+"?([^"]+)"?\s*$', line)
            if simple_match and ':' not in line.split('-', 1)[1].split('"')[0]:
                current = simple_match.group(1)
            else:
                kv_match = re.match(r'^\s{6}-\s+(\w+):\s*"?([^"]*)"?\s*$', line)
                if kv_match:
                    current = {}
                    current[kv_match.group(1)] = kv_match.group(2)
        elif current is not None and isinstance(current, dict):
            kv_match = re.match(r'^\s{8,}(\w+):\s*"?([^"]*)"?\s*$', line)
            if kv_match:
                val = kv_match.group(2)
                current[kv_match.group(1)] = int(val) if re.match(r'^\d+$', val) else val
            arr_match = re.match(r'^\s{10,}-\s+"?([^"]+)"?\s*$', line)
            if arr_match:
                keys = list(current.keys())
                if keys:
                    last_key = keys[-1]
                    if not isinstance(current[last_key], list):
                        current[last_key] = [current[last_key]] if current[last_key] else []
                    current[last_key].append(arr_match.group(1))

    if current is not None:
        items.append(current)

    return items


# ─── Frontmatter CRUD commands ────────────────────────────────────────────────

FRONTMATTER_SCHEMAS = {
    'plan': {'required': ['phase', 'plan', 'type', 'wave', 'depends_on', 'files_modified', 'autonomous', 'must_haves']},
    'summary': {'required': ['phase', 'plan', 'subsystem', 'tags', 'duration', 'completed']},
    'verification': {'required': ['phase', 'verified', 'status', 'score']},
}


def cmd_frontmatter_get(cwd, file_path, field, raw):
    if not file_path:
        error('file path required')
    full_path = file_path if os.path.isabs(file_path) else os.path.join(cwd, file_path)
    content = safe_read_file(full_path)
    if not content:
        output({'error': 'File not found', 'path': file_path}, raw)
        return
    fm = extract_frontmatter(content)
    if field:
        value = fm.get(field)
        if value is None and field not in fm:
            output({'error': 'Field not found', 'field': field}, raw)
            return
        output({field: value}, raw, json.dumps(value))
    else:
        output(fm, raw)


def cmd_frontmatter_set(cwd, file_path, field, value, raw):
    if not file_path or not field or value is None:
        error('file, field, and value required')
    full_path = file_path if os.path.isabs(file_path) else os.path.join(cwd, file_path)
    if not os.path.exists(full_path):
        output({'error': 'File not found', 'path': file_path}, raw)
        return
    with open(full_path, 'r', encoding='utf-8') as f:
        content = f.read()
    fm = extract_frontmatter(content)
    try:
        parsed_value = json.loads(value)
    except (ValueError, TypeError):
        parsed_value = value
    fm[field] = parsed_value
    new_content = splice_frontmatter(content, fm)
    with open(full_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    output({'updated': True, 'field': field, 'value': parsed_value}, raw, 'true')


def cmd_frontmatter_merge(cwd, file_path, data, raw):
    if not file_path or not data:
        error('file and data required')
    full_path = file_path if os.path.isabs(file_path) else os.path.join(cwd, file_path)
    if not os.path.exists(full_path):
        output({'error': 'File not found', 'path': file_path}, raw)
        return
    with open(full_path, 'r', encoding='utf-8') as f:
        content = f.read()
    fm = extract_frontmatter(content)
    try:
        merge_data = json.loads(data)
    except (ValueError, TypeError):
        error('Invalid JSON for --data')
        return
    fm.update(merge_data)
    new_content = splice_frontmatter(content, fm)
    with open(full_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    output({'merged': True, 'fields': list(merge_data.keys())}, raw, 'true')


def cmd_frontmatter_validate(cwd, file_path, schema_name, raw):
    if not file_path or not schema_name:
        error('file and schema required')
    schema = FRONTMATTER_SCHEMAS.get(schema_name)
    if not schema:
        error('Unknown schema: %s. Available: %s' % (schema_name, ', '.join(FRONTMATTER_SCHEMAS.keys())))
    full_path = file_path if os.path.isabs(file_path) else os.path.join(cwd, file_path)
    content = safe_read_file(full_path)
    if not content:
        output({'error': 'File not found', 'path': file_path}, raw)
        return
    fm = extract_frontmatter(content)
    missing = [f for f in schema['required'] if f not in fm]
    present = [f for f in schema['required'] if f in fm]
    output(
        {'valid': len(missing) == 0, 'missing': missing, 'present': present, 'schema': schema_name},
        raw,
        'valid' if len(missing) == 0 else 'invalid'
    )
