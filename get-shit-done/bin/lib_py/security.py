"""Security — Input validation, path traversal prevention, and prompt injection guards."""

import json
import os
import re


# ─── Path Traversal Prevention ───────────────────────────────────────────────

def validate_path(file_path, base_dir, opts=None):
    """Validate that a file path resolves within an allowed base directory."""
    if opts is None:
        opts = {}

    if not file_path or not isinstance(file_path, str):
        return {'safe': False, 'resolved': '', 'error': 'Empty or invalid file path'}
    if not base_dir or not isinstance(base_dir, str):
        return {'safe': False, 'resolved': '', 'error': 'Empty or invalid base directory'}
    if '\0' in file_path:
        return {'safe': False, 'resolved': '', 'error': 'Null byte in file path'}
    if '\0' in base_dir:
        return {'safe': False, 'resolved': '', 'error': 'Null byte in base directory'}

    try:
        resolved_base = os.path.realpath(base_dir)
    except OSError:
        resolved_base = os.path.normpath(base_dir)

    if os.path.isabs(file_path):
        if not opts.get('allowAbsolute', False):
            return {'safe': False, 'resolved': '', 'error': 'Absolute paths not allowed'}
        target = file_path
    else:
        target = os.path.join(resolved_base, file_path)

    if os.path.exists(target):
        try:
            resolved = os.path.realpath(target)
        except OSError:
            resolved = os.path.normpath(target)
    else:
        parent = os.path.dirname(target)
        if os.path.exists(parent):
            try:
                resolved = os.path.join(os.path.realpath(parent), os.path.basename(target))
            except OSError:
                resolved = os.path.normpath(target)
        else:
            resolved = os.path.normpath(target)

    resolved_norm = os.path.normpath(resolved)
    base_norm = os.path.normpath(resolved_base)

    if not (resolved_norm == base_norm or resolved_norm.startswith(base_norm + os.sep)):
        return {'safe': False, 'resolved': resolved_norm, 'error': 'Path escapes base directory'}

    return {'safe': True, 'resolved': resolved_norm}


def require_safe_path(file_path, base_dir, label='Path', opts=None):
    """Convenience wrapper that raises ValueError if path is unsafe."""
    result = validate_path(file_path, base_dir, opts)
    if not result['safe']:
        raise ValueError('%s: %s' % (label, result.get('error', 'unsafe path')))
    return result['resolved']


# ─── Prompt Injection Detection ──────────────────────────────────────────────

INJECTION_PATTERNS = [
    (r'ignore\s+(all\s+)?previous\s+instructions', 'ignore previous instructions'),
    (r'ignore\s+(all\s+)?above\s+instructions', 'ignore above instructions'),
    (r'disregard\s+(all\s+)?previous', 'disregard previous'),
    (r'forget\s+(all\s+)?(your\s+)?instructions', 'forget instructions'),
    (r'override\s+(system|previous)\s+(prompt|instructions)', 'override prompt'),
    (r'you\s+are\s+now\s+(?:a|an|the)\s+', 'role reassignment'),
    (r'act\s+as\s+(?:a|an|the)\s+(?!plan|phase|wave)', 'role impersonation'),
    (r'pretend\s+(?:you(?:\'re| are)\s+|to\s+be\s+)', 'pretend impersonation'),
    (r'from\s+now\s+on,?\s+you\s+(?:are|will|should|must)', 'instruction override'),
    (r'(?:print|output|reveal|show|display|repeat)\s+(?:your\s+)?(?:system\s+)?(?:prompt|instructions)',
     'prompt extraction'),
    (r'what\s+(?:are|is)\s+your\s+(?:system\s+)?(?:prompt|instructions)', 'prompt query'),
    (r'</?(?:system|assistant|human)>', 'xml role tag'),
    (r'\[SYSTEM\]', 'system marker'),
    (r'\[INST\]', 'inst marker'),
    (r'<<\s*SYS\s*>>', 'sys marker'),
    (r'(?:send|post|fetch|curl|wget)\s+(?:to|from)\s+https?://', 'data exfiltration'),
    (r'(?:base64|btoa|encode)\s+(?:and\s+)?(?:send|exfiltrate|output)', 'encoded exfiltration'),
    (r'(?:run|execute|call|invoke)\s+(?:the\s+)?(?:bash|shell|exec|spawn)\s+(?:tool|command)',
     'tool invocation'),
]

_COMPILED_PATTERNS = [(re.compile(p, re.IGNORECASE), desc) for p, desc in INJECTION_PATTERNS]

_SUSPICIOUS_UNICODE = re.compile(r'[\u200b-\u200f\u2028-\u202f\ufeff\u00ad]')


def scan_for_injection(text, opts=None):
    """Scan text for prompt injection patterns."""
    if opts is None:
        opts = {}
    if not text or not isinstance(text, str):
        return {'clean': True, 'findings': []}

    findings = []
    for pattern, desc in _COMPILED_PATTERNS:
        if pattern.search(text):
            findings.append(desc)

    if opts.get('strict', False):
        if _SUSPICIOUS_UNICODE.search(text):
            findings.append('suspicious unicode characters')
        if len(text) > 50000:
            findings.append('excessive length (potential prompt stuffing)')

    return {'clean': len(findings) == 0, 'findings': findings}


# ─── Sanitization ────────────────────────────────────────────────────────────

_ZERO_WIDTH_RE = re.compile(r'[\u200b-\u200f\u2028-\u202f\ufeff\u00ad]')
_XML_ROLE_TAGS = re.compile(r'<(/?)(?:system|assistant|human)>', re.IGNORECASE)
_SYSTEM_MARKER = re.compile(r'\[SYSTEM\]', re.IGNORECASE)
_INST_MARKER = re.compile(r'\[INST\]', re.IGNORECASE)
_SYS_ANGLE = re.compile(r'<<\s*SYS\s*>>', re.IGNORECASE)
_PROTOCOL_LEAK_1 = re.compile(
    r'^\s*(?:assistant|user|system)\s+to=[^:\s]+:[^\n]+$', re.IGNORECASE | re.MULTILINE)
_PROTOCOL_LEAK_2 = re.compile(
    r'^\s*<\|(?:assistant|user|system)[^|]*\|>\s*$', re.IGNORECASE | re.MULTILINE)


def sanitize_for_prompt(text):
    """Neutralize control characters and instruction-mimicking patterns."""
    if not text or not isinstance(text, str):
        return text or ''
    result = _ZERO_WIDTH_RE.sub('', text)
    result = _XML_ROLE_TAGS.sub(lambda m: '\uff1c%s-text\uff1e' % m.group(0)[1:-1], result)
    result = _SYSTEM_MARKER.sub('[SYSTEM-TEXT]', result)
    result = _INST_MARKER.sub('[INST-TEXT]', result)
    result = _SYS_ANGLE.sub('\u00abSYS-TEXT\u00bb', result)
    return result


def sanitize_for_display(text):
    """Remove protocol-like leak markers for safe display."""
    if not text or not isinstance(text, str):
        return text or ''
    result = sanitize_for_prompt(text)
    lines = result.split('\n')
    filtered = [ln for ln in lines
                if not _PROTOCOL_LEAK_1.match(ln) and not _PROTOCOL_LEAK_2.match(ln)]
    return '\n'.join(filtered)


# ─── Shell & JSON Safety ─────────────────────────────────────────────────────

def validate_shell_arg(value, label='argument'):
    """Validate a string is safe when quoted for shell execution."""
    if not value or not isinstance(value, str):
        raise ValueError('%s: empty or invalid value' % label)
    if '\0' in value:
        raise ValueError('%s: contains null byte' % label)
    if ('$(' in value or '`' in value) and ('$' in value or '`' in value):
        raise ValueError('%s: potential command substitution' % label)
    return value


def safe_json_parse(text, opts=None):
    """Safely parse JSON with error handling and size limits."""
    if opts is None:
        opts = {}
    max_length = opts.get('maxLength', 1048576)
    label = opts.get('label', 'JSON')

    if not text or not isinstance(text, str):
        return {'ok': False, 'error': '%s: empty or invalid input' % label}
    if len(text) > max_length:
        return {'ok': False, 'error': '%s: exceeds maximum length (%d bytes)' % (label, max_length)}
    try:
        value = json.loads(text)
        return {'ok': True, 'value': value}
    except (json.JSONDecodeError, ValueError) as exc:
        return {'ok': False, 'error': '%s: parse error — %s' % (label, str(exc))}


# ─── Phase & Field Validation ────────────────────────────────────────────────

_PHASE_STANDARD = re.compile(r'^\d{1,4}[A-Z]?(?:\.\d{1,3})*$', re.IGNORECASE)
_PHASE_CUSTOM = re.compile(r'^[A-Z][A-Z0-9]*(?:-[A-Z0-9]+){1,4}$', re.IGNORECASE)
_FIELD_NAME = re.compile(r'^[A-Za-z][A-Za-z0-9 _.\-/]{0,60}$')


def validate_phase_number(phase):
    """Validate phase number arguments."""
    if not phase or not isinstance(phase, str):
        return {'valid': False, 'error': 'Empty or invalid phase number'}
    trimmed = phase.strip()
    if _PHASE_STANDARD.match(trimmed):
        return {'valid': True, 'normalized': trimmed}
    if len(trimmed) <= 30 and _PHASE_CUSTOM.match(trimmed):
        return {'valid': True, 'normalized': trimmed}
    return {'valid': False, 'error': 'Invalid phase number format: %s' % phase}


def validate_field_name(field):
    """Validate STATE.md field names to prevent regex injection."""
    if not field or not isinstance(field, str):
        return {'valid': False, 'error': 'Empty or invalid field name'}
    if _FIELD_NAME.match(field):
        return {'valid': True}
    return {'valid': False, 'error': 'Invalid field name: %s' % field}
