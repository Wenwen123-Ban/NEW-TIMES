from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[2]
DB_FILES = {
    'books': ROOT / 'books.json',
    'admins': ROOT / 'admins.json',
    'users': ROOT / 'users.json',
    'transactions': ROOT / 'transactions.json',
    'categories': ROOT / 'categories.json',
    'config': ROOT / 'system_config.json',
    'blocked_dates': ROOT / 'blocked_dates.json',
}


def _default(key: str):
    return {} if key == 'config' else []


def read_json(key: str):
    path = DB_FILES[key]
    if not path.exists():
        return _default(key)
    with path.open('r', encoding='utf-8') as handle:
        return json.load(handle)


def write_json(key: str, payload):
    path = DB_FILES[key]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8') as handle:
        json.dump(payload, handle, indent=4, ensure_ascii=False)


def now_str() -> str:
    return datetime.now().strftime('%Y-%m-%d %H:%M')
