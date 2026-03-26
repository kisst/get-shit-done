"""Model Profiles — Agent-to-model mapping with quality/balanced/budget tiers."""

from .core import MODEL_PROFILES

VALID_PROFILES = ['quality', 'balanced', 'budget']

# Extended profiles for newer agents not in core.MODEL_PROFILES
EXTENDED_PROFILES = {
    'gsd-nyquist-auditor':  {'quality': 'sonnet', 'balanced': 'sonnet', 'budget': 'haiku'},
    'gsd-ui-researcher':    {'quality': 'opus',   'balanced': 'sonnet', 'budget': 'haiku'},
    'gsd-ui-checker':       {'quality': 'sonnet', 'balanced': 'sonnet', 'budget': 'haiku'},
    'gsd-ui-auditor':       {'quality': 'opus',   'balanced': 'sonnet', 'budget': 'haiku'},
}


def _all_profiles():
    merged = dict(MODEL_PROFILES)
    merged.update(EXTENDED_PROFILES)
    return merged


def get_agent_to_model_map_for_profile(normalized_profile):
    """Get agent-to-model mapping for a specific profile tier."""
    if normalized_profile not in VALID_PROFILES:
        normalized_profile = 'balanced'
    profiles = _all_profiles()
    return {agent: tiers.get(normalized_profile, 'sonnet')
            for agent, tiers in profiles.items()}


def format_agent_to_model_map_as_table(agent_to_model_map):
    """Format agent-to-model mapping as a human-readable ASCII table."""
    if not agent_to_model_map:
        return ''

    agent_col = max(len(a) for a in agent_to_model_map)
    model_col = max(len(m) for m in agent_to_model_map.values())
    agent_col = max(agent_col, 5)
    model_col = max(model_col, 5)

    sep = '\u2500' * (agent_col + 2) + '\u253c' + '\u2500' * (model_col + 2)
    lines = [' %-*s \u2502 %-*s' % (agent_col, 'Agent', model_col, 'Model'), sep]
    for agent in sorted(agent_to_model_map):
        lines.append(' %-*s \u2502 %-*s' % (
            agent_col, agent, model_col, agent_to_model_map[agent]))

    return '\n'.join(lines)
