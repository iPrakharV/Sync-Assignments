import os
import json
import copy

ROOT = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(ROOT, 'config.json')

DEFAULTS = {
    'senders': ['d2lsupport@purdue.brightspace.com'],
    'lookback_days': 3,
    'timezone': 'America/New_York',
    'notifications': 'always',  # always | changes | errors | never
    'todoist': {
        'enabled': True,
        'project': 'Inbox',
        'section': None,
        'priority': 2,
        'assign_to_me': True,  # only takes effect in shared projects
        'type_labels': True,
        'course_labels': {},
        'label_colors': {},
    },
    'google_tasks': {
        'enabled': False,
    },
}


def _merge(base, override):
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config(path=CONFIG_PATH):
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"No config found at {path}. Copy config.example.json to config.json and fill it in.")
    with open(path, 'r') as f:
        return _merge(DEFAULTS, json.load(f))
