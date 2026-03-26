"""Profile Output — Profile rendering and artifact generation."""

import json
import os
import re

from .core import output, error, safe_read_file


# ─── Constants ───────────────────────────────────────────────────────────────

DIMENSION_KEYS = [
    'communication_style',
    'decision_speed',
    'explanation_depth',
    'debugging_approach',
    'ux_philosophy',
    'vendor_philosophy',
    'frustration_triggers',
    'learning_style',
]

PROFILING_QUESTIONS = [
    {
        'dimension': 'communication_style',
        'question': 'When Claude explains a solution, I prefer:',
        'options': {
            'a': {'rating': 'terse-direct', 'confidence': 'HIGH'},
            'b': {'rating': 'detailed-educational', 'confidence': 'HIGH'},
            'c': {'rating': 'balanced', 'confidence': 'MEDIUM'},
            'd': {'rating': 'mixed', 'confidence': 'LOW'},
        },
    },
    {
        'dimension': 'decision_speed',
        'question': 'When choosing between approaches, I want Claude to:',
        'options': {
            'a': {'rating': 'fast-decisive', 'confidence': 'HIGH'},
            'b': {'rating': 'thorough-deliberate', 'confidence': 'HIGH'},
            'c': {'rating': 'adaptive', 'confidence': 'MEDIUM'},
            'd': {'rating': 'mixed', 'confidence': 'LOW'},
        },
    },
    {
        'dimension': 'explanation_depth',
        'question': 'When explaining code changes, I want:',
        'options': {
            'a': {'rating': 'minimal', 'confidence': 'HIGH'},
            'b': {'rating': 'comprehensive', 'confidence': 'HIGH'},
            'c': {'rating': 'contextual', 'confidence': 'MEDIUM'},
            'd': {'rating': 'mixed', 'confidence': 'LOW'},
        },
    },
    {
        'dimension': 'debugging_approach',
        'question': 'When debugging, I prefer Claude to:',
        'options': {
            'a': {'rating': 'systematic', 'confidence': 'HIGH'},
            'b': {'rating': 'intuitive', 'confidence': 'HIGH'},
            'c': {'rating': 'hybrid', 'confidence': 'MEDIUM'},
            'd': {'rating': 'mixed', 'confidence': 'LOW'},
        },
    },
    {
        'dimension': 'ux_philosophy',
        'question': 'For UI/UX decisions, I lean toward:',
        'options': {
            'a': {'rating': 'function-first', 'confidence': 'HIGH'},
            'b': {'rating': 'design-first', 'confidence': 'HIGH'},
            'c': {'rating': 'balanced', 'confidence': 'MEDIUM'},
            'd': {'rating': 'mixed', 'confidence': 'LOW'},
        },
    },
    {
        'dimension': 'vendor_philosophy',
        'question': 'For third-party dependencies, I prefer:',
        'options': {
            'a': {'rating': 'minimal-deps', 'confidence': 'HIGH'},
            'b': {'rating': 'leverage-ecosystem', 'confidence': 'HIGH'},
            'c': {'rating': 'pragmatic', 'confidence': 'MEDIUM'},
            'd': {'rating': 'mixed', 'confidence': 'LOW'},
        },
    },
    {
        'dimension': 'frustration_triggers',
        'question': 'What frustrates me most when working with AI:',
        'options': {
            'a': {'rating': 'verbosity', 'confidence': 'HIGH'},
            'b': {'rating': 'assumptions', 'confidence': 'HIGH'},
            'c': {'rating': 'slowness', 'confidence': 'MEDIUM'},
            'd': {'rating': 'mixed', 'confidence': 'LOW'},
        },
    },
    {
        'dimension': 'learning_style',
        'question': 'When learning new concepts, I prefer:',
        'options': {
            'a': {'rating': 'examples-first', 'confidence': 'HIGH'},
            'b': {'rating': 'theory-first', 'confidence': 'HIGH'},
            'c': {'rating': 'interactive', 'confidence': 'MEDIUM'},
            'd': {'rating': 'mixed', 'confidence': 'LOW'},
        },
    },
]

CLAUDE_INSTRUCTIONS = {
    'communication_style': {
        'terse-direct': 'Keep responses concise and action-oriented. Lead with code, not explanation.',
        'detailed-educational': 'Explain reasoning and context. Help the user learn, not just solve.',
        'balanced': 'Match response length to complexity. Brief for simple tasks, detailed for complex ones.',
        'mixed': 'Adapt communication style to the specific task at hand.',
    },
    'decision_speed': {
        'fast-decisive': 'Make decisions quickly. Suggest the best option rather than listing alternatives.',
        'thorough-deliberate': 'Present options with trade-offs before committing to an approach.',
        'adaptive': 'Quick decisions for routine tasks, deliberate for architectural choices.',
        'mixed': 'Adapt decision speed to context.',
    },
    'explanation_depth': {
        'minimal': 'Skip explanations unless asked. Let the code speak for itself.',
        'comprehensive': 'Explain the why behind changes, not just the what.',
        'contextual': 'Explain when the change is non-obvious; skip for routine modifications.',
        'mixed': 'Adapt explanation depth to context.',
    },
    'debugging_approach': {
        'systematic': 'Debug methodically: reproduce, isolate, hypothesize, verify.',
        'intuitive': 'Start with likely causes based on pattern recognition.',
        'hybrid': 'Use intuition for initial direction, systematic methods for verification.',
        'mixed': 'Adapt debugging approach to the problem.',
    },
    'ux_philosophy': {
        'function-first': 'Prioritize functionality and performance over visual polish.',
        'design-first': 'Prioritize user experience and visual design.',
        'balanced': 'Balance functionality with user experience.',
        'mixed': 'Adapt UX priority to context.',
    },
    'vendor_philosophy': {
        'minimal-deps': 'Prefer standard library and minimal dependencies.',
        'leverage-ecosystem': 'Use well-maintained packages to avoid reinventing the wheel.',
        'pragmatic': 'Choose based on specific needs — build simple things, import complex ones.',
        'mixed': 'Adapt dependency decisions to context.',
    },
    'frustration_triggers': {
        'verbosity': 'Never pad responses. If it can be said in one line, use one line.',
        'assumptions': 'Always verify before acting. Ask when uncertain rather than assuming.',
        'slowness': 'Prioritize speed of response. Get to the solution quickly.',
        'mixed': 'Balance all factors.',
    },
    'learning_style': {
        'examples-first': 'Lead with working code examples, then explain the pattern.',
        'theory-first': 'Explain the concept first, then show implementation.',
        'interactive': 'Build understanding incrementally through guided exploration.',
        'mixed': 'Adapt teaching style to the topic.',
    },
}

SENSITIVE_PATTERNS = [
    re.compile(r'sk-[a-zA-Z0-9]{20,}'),
    re.compile(r'ghp_[a-zA-Z0-9]{36}'),
    re.compile(r'gho_[a-zA-Z0-9]{36}'),
    re.compile(r'Bearer\s+[a-zA-Z0-9._\-]{20,}'),
    re.compile(r'(?:password|secret|token|api[_-]?key)\s*[:=]\s*\S+', re.IGNORECASE),
    re.compile(r'/home/[a-zA-Z0-9_]+'),
    re.compile(r'/Users/[a-zA-Z0-9_]+'),
    re.compile(r'C:\\Users\\[a-zA-Z0-9_]+'),
]


# ─── Section Management ──────────────────────────────────────────────────────

def extract_section_content(file_content, section_name):
    """Extract body of a GSD-managed section from CLAUDE.md."""
    start_re = re.compile(r'<!--\s*GSD:%s-start' % re.escape(section_name), re.IGNORECASE)
    end_re = re.compile(r'<!--\s*GSD:%s-end\s*-->' % re.escape(section_name), re.IGNORECASE)
    start_m = start_re.search(file_content)
    if not start_m:
        return None
    after = file_content[start_m.end():]
    close_m = re.search(r'-->', after)
    if close_m:
        after = after[close_m.end():]
    end_m = end_re.search(after)
    if not end_m:
        return None
    return after[:end_m.start()].strip()


def build_section(section_name, source_file, content):
    """Wrap content in GSD section markers."""
    return '\n'.join([
        '<!-- GSD:%s-start source="%s" -->' % (section_name, source_file),
        content,
        '<!-- GSD:%s-end -->' % section_name,
    ])


def update_section(file_content, section_name, new_content):
    """Replace or append a GSD-managed section in a file."""
    start_re = re.compile(
        r'<!--\s*GSD:%s-start[^>]*-->' % re.escape(section_name), re.IGNORECASE)
    end_re = re.compile(
        r'<!--\s*GSD:%s-end\s*-->' % re.escape(section_name), re.IGNORECASE)

    start_m = start_re.search(file_content)
    if start_m:
        end_m = end_re.search(file_content, start_m.end())
        if end_m:
            updated = file_content[:start_m.start()] + new_content + file_content[end_m.end():]
            return {'content': updated, 'action': 'replaced'}

    return {'content': file_content.rstrip() + '\n\n' + new_content + '\n', 'action': 'appended'}


def detect_manual_edit(file_content, section_name, expected_content):
    """Check if a GSD-managed section has been manually edited."""
    current = extract_section_content(file_content, section_name)
    if current is None:
        return False
    norm_current = re.sub(r'\s+', ' ', current).strip()
    norm_expected = re.sub(r'\s+', ' ', expected_content).strip()
    return norm_current != norm_expected


# ─── Content Generators ──────────────────────────────────────────────────────

def _extract_markdown_section(content, heading):
    pattern = re.compile(r'^##\s+%s\s*$' % re.escape(heading), re.MULTILINE | re.IGNORECASE)
    m = pattern.search(content)
    if not m:
        return None
    rest = content[m.end():]
    next_h = re.search(r'^##\s', rest, re.MULTILINE)
    section = rest[:next_h.start()] if next_h else rest
    return section.strip()


def generate_project_section(cwd):
    content = safe_read_file(os.path.join(cwd, '.planning', 'PROJECT.md'))
    if not content:
        return {'content': '<!-- TODO: Add project description -->', 'source': 'PROJECT.md',
                'hasFallback': True}

    parts = []
    for heading in ('What This Is', 'Core Value', 'Constraints'):
        section = _extract_markdown_section(content, heading)
        if section:
            parts.append('### %s\n%s' % (heading, section))

    title_m = re.search(r'^#\s+(.+)', content, re.MULTILINE)
    if title_m:
        parts.insert(0, '## %s' % title_m.group(1).strip())

    return {
        'content': '\n\n'.join(parts) if parts else content[:500],
        'source': 'PROJECT.md',
        'hasFallback': False,
    }


def generate_stack_section(cwd):
    for rel in ('codebase/STACK.md', 'research/STACK.md'):
        content = safe_read_file(os.path.join(cwd, '.planning', rel))
        if content:
            return {'content': content[:2000], 'source': rel, 'hasFallback': False}
    return {'content': '<!-- TODO: Add technology stack -->', 'source': 'codebase/STACK.md',
            'hasFallback': True}


def generate_conventions_section(cwd):
    content = safe_read_file(os.path.join(cwd, '.planning', 'codebase', 'CONVENTIONS.md'))
    if content:
        return {'content': content[:2000], 'source': 'CONVENTIONS.md', 'hasFallback': False}
    return {'content': '<!-- TODO: Add conventions -->', 'source': 'CONVENTIONS.md',
            'hasFallback': True}


def generate_architecture_section(cwd):
    content = safe_read_file(os.path.join(cwd, '.planning', 'codebase', 'ARCHITECTURE.md'))
    if content:
        return {'content': content[:2000], 'source': 'ARCHITECTURE.md', 'hasFallback': False}
    return {'content': '<!-- TODO: Add architecture -->', 'source': 'ARCHITECTURE.md',
            'hasFallback': True}


def generate_workflow_section():
    return {
        'content': (
            '## GSD Workflow\n\n'
            'This project uses the GSD (Get Shit Done) workflow.\n'
            'Use `/gsd:` commands as entry points for all planning and execution.\n'
            'Do not bypass the workflow by editing planning files directly.'
        ),
        'source': 'GSD defaults',
        'hasFallback': False,
    }


def _redact_sensitive(text):
    result = text
    for pattern in SENSITIVE_PATTERNS:
        result = pattern.sub('[REDACTED]', result)
    return result


# ─── Commands ────────────────────────────────────────────────────────────────

def cmd_write_profile(cwd, options, raw):
    """Render analysis JSON into USER-PROFILE.md."""
    input_path = options.get('input')
    if not input_path:
        error('--input is required')
        return

    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            analysis = json.load(f)
    except (IOError, OSError, ValueError) as exc:
        error('Cannot read analysis file: %s' % str(exc))
        return

    template_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        'templates', 'user-profile.md')
    template = safe_read_file(template_path)
    if not template:
        template = '# User Profile\n\n{{DIMENSIONS}}\n'

    dimensions = analysis.get('dimensions', {})
    dim_lines = []
    confidence_counts = {'HIGH': 0, 'MEDIUM': 0, 'LOW': 0}
    for dim_key in DIMENSION_KEYS:
        dim = dimensions.get(dim_key, {})
        rating = dim.get('rating', 'unknown')
        confidence = dim.get('confidence', 'LOW')
        confidence_counts[confidence] = confidence_counts.get(confidence, 0) + 1
        dim_lines.append('- **%s:** %s (confidence: %s)' % (
            dim_key.replace('_', ' ').title(), rating, confidence))

    redacted = _redact_sensitive(json.dumps(analysis, indent=2))
    redaction_count = redacted.count('[REDACTED]')

    content = template.replace('{{DIMENSIONS}}', '\n'.join(dim_lines))

    output_path = options.get('output') or os.path.join(
        os.path.expanduser('~'), '.claude', 'get-shit-done', 'USER-PROFILE.md')
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(content)

    output({
        'profile_path': output_path,
        'dimensions_scored': len([d for d in dimensions if d in DIMENSION_KEYS]),
        'confidence_counts': confidence_counts,
        'redactions': redaction_count,
    }, raw)


def cmd_profile_questionnaire(options, raw):
    """Return profiling questions or score answered responses."""
    answers_str = options.get('answers')
    if not answers_str:
        questions = []
        for q in PROFILING_QUESTIONS:
            questions.append({
                'dimension': q['dimension'],
                'question': q['question'],
                'options': {k: v['rating'] for k, v in q['options'].items()},
            })
        output({'questions': questions}, raw)
        return

    answers = [a.strip().lower() for a in answers_str.split(',')]
    if len(answers) != len(PROFILING_QUESTIONS):
        error('Expected %d answers, got %d' % (len(PROFILING_QUESTIONS), len(answers)))
        return

    dimensions = {}
    claude_instructions = {}
    for i, q in enumerate(PROFILING_QUESTIONS):
        answer = answers[i]
        opt = q['options'].get(answer)
        if not opt:
            error('Invalid answer "%s" for question %d' % (answer, i + 1))
            return

        dim = q['dimension']
        rating = opt['rating']
        confidence = opt['confidence']
        dimensions[dim] = {'rating': rating, 'confidence': confidence}

        inst = CLAUDE_INSTRUCTIONS.get(dim, {}).get(rating)
        if inst:
            claude_instructions[dim] = inst

    output({
        'dimensions': dimensions,
        'claude_instructions': claude_instructions,
    }, raw)


def cmd_generate_dev_preferences(cwd, options, raw):
    """Render analysis JSON into dev-preferences.md command artifact."""
    analysis_path = options.get('analysis')
    if not analysis_path:
        error('--analysis is required')
        return

    try:
        with open(analysis_path, 'r', encoding='utf-8') as f:
            analysis = json.load(f)
    except (IOError, OSError, ValueError) as exc:
        error('Cannot read analysis file: %s' % str(exc))
        return

    dimensions = analysis.get('dimensions', {})
    directives = []
    for dim_key in DIMENSION_KEYS:
        dim = dimensions.get(dim_key, {})
        rating = dim.get('rating', 'unknown')
        confidence = dim.get('confidence', 'LOW')
        inst = CLAUDE_INSTRUCTIONS.get(dim_key, {}).get(rating, '')
        if inst:
            directives.append('- [%s] %s: %s' % (confidence, dim_key.replace('_', ' ').title(), inst))

    template_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        'templates', 'dev-preferences.md')
    template = safe_read_file(template_path)
    if not template:
        template = '# Developer Preferences\n\n{{DIRECTIVES}}\n'

    content = template.replace('{{DIRECTIVES}}', '\n'.join(directives))

    output_path = options.get('output') or os.path.join(
        os.path.expanduser('~'), '.claude', 'commands', 'gsd', 'dev-preferences.md')
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(content)

    output({
        'command_path': output_path,
        'dimensions_included': len(directives),
        'source': analysis_path,
    }, raw)


def cmd_generate_claude_profile(cwd, options, raw):
    """Generate Developer Profile section for CLAUDE.md."""
    analysis_path = options.get('analysis')
    if not analysis_path:
        error('--analysis is required')
        return

    try:
        with open(analysis_path, 'r', encoding='utf-8') as f:
            analysis = json.load(f)
    except (IOError, OSError, ValueError) as exc:
        error('Cannot read analysis file: %s' % str(exc))
        return

    dimensions = analysis.get('dimensions', {})
    table_lines = ['| Dimension | Rating | Confidence |', '|-----------|--------|------------|']
    directive_lines = []
    for dim_key in DIMENSION_KEYS:
        dim = dimensions.get(dim_key, {})
        rating = dim.get('rating', 'unknown')
        confidence = dim.get('confidence', 'LOW')
        table_lines.append('| %s | %s | %s |' % (
            dim_key.replace('_', ' ').title(), rating, confidence))
        inst = CLAUDE_INSTRUCTIONS.get(dim_key, {}).get(rating, '')
        if inst:
            directive_lines.append('- %s' % inst)

    section_content = '## Developer Profile\n\n' + '\n'.join(table_lines)
    if directive_lines:
        section_content += '\n\n### Directives\n\n' + '\n'.join(directive_lines)

    wrapped = build_section('profile', analysis_path, section_content)

    is_global = options.get('global', False)
    if is_global:
        claude_md_path = os.path.join(os.path.expanduser('~'), '.claude', 'CLAUDE.md')
    else:
        claude_md_path = options.get('output') or os.path.join(cwd, 'CLAUDE.md')

    existing = safe_read_file(claude_md_path) or ''
    if existing:
        result = update_section(existing, 'profile', wrapped)
        action = result['action']
        final = result['content']
    else:
        final = wrapped
        action = 'created'

    os.makedirs(os.path.dirname(claude_md_path), exist_ok=True)
    with open(claude_md_path, 'w', encoding='utf-8') as f:
        f.write(final)

    output({
        'claude_md_path': claude_md_path,
        'action': action,
        'dimensions_included': len([d for d in dimensions if d in DIMENSION_KEYS]),
        'is_global': is_global,
    }, raw)


def cmd_generate_claude_md(cwd, options, raw):
    """Generate or update entire CLAUDE.md with all managed sections."""
    claude_md_path = options.get('output') or os.path.join(cwd, 'CLAUDE.md')
    auto_mode = options.get('auto', False)

    generators = {
        'project': lambda: generate_project_section(cwd),
        'stack': lambda: generate_stack_section(cwd),
        'conventions': lambda: generate_conventions_section(cwd),
        'architecture': lambda: generate_architecture_section(cwd),
        'workflow': generate_workflow_section,
    }

    existing = safe_read_file(claude_md_path) or ''
    sections_generated = []
    sections_fallback = []
    sections_skipped = []

    content = existing
    for name, gen_fn in generators.items():
        result = gen_fn()
        if result['hasFallback']:
            sections_fallback.append(name)

        wrapped = build_section(name, result['source'], result['content'])

        if existing and auto_mode and detect_manual_edit(existing, name, result['content']):
            sections_skipped.append(name)
            continue

        if existing:
            update_result = update_section(content, name, wrapped)
            content = update_result['content']
        else:
            content = content + ('\n\n' if content else '') + wrapped

        sections_generated.append(name)

    os.makedirs(os.path.dirname(os.path.abspath(claude_md_path)), exist_ok=True)
    with open(claude_md_path, 'w', encoding='utf-8') as f:
        f.write(content)

    action = 'updated' if existing else 'created'
    output({
        'claude_md_path': claude_md_path,
        'action': action,
        'sections_generated': sections_generated,
        'sections_fallback': sections_fallback,
        'sections_skipped': sections_skipped,
        'sections_total': len(generators),
        'profile_status': 'placeholder' if not existing else 'existing',
    }, raw)
