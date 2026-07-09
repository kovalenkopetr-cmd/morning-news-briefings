#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None

DEFAULT_LIMIT = 3500
STATE_DIR = Path.home() / '.cache' / 'hermes-news-briefings'
STATE_FILE = STATE_DIR / 'delivery-state.json'
DATE_RE = re.compile(r'^#\s+.*?—\s*(\d{4}-\d{2}-\d{2})\s*$', re.M)


@dataclass
class Config:
    raw_url: str
    send_only_if_file_changed: bool = True
    include_header: bool = True
    include_source_link: bool = False
    split_long_messages: bool = True
    max_message_length: int = DEFAULT_LIMIT


def _load_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    text = path.read_text(encoding='utf-8')
    if not text.strip():
        return {}
    if yaml is not None:
        data = yaml.safe_load(text) or {}
        return data if isinstance(data, dict) else {}
    return {}


def _read_config(repo_root: Path, raw_url_arg: Optional[str]) -> Config:
    cfg_path = Path(os.environ.get('BRIEFING_CONFIG', repo_root / 'config' / 'hermes.example.yaml'))
    data = _load_yaml(cfg_path)
    source = data.get('source', {}) if isinstance(data.get('source', {}), dict) else {}
    delivery = data.get('delivery', {}) if isinstance(data.get('delivery', {}), dict) else {}
    behavior = data.get('behavior', {}) if isinstance(data.get('behavior', {}), dict) else {}
    repo = str(source.get('repo', 'OWNER/hermes-news-briefings'))
    branch = str(source.get('branch', 'main'))
    file_path = str(source.get('file', 'latest/briefing.md'))
    raw_url = raw_url_arg or os.environ.get('BRIEFING_RAW_URL') or f'https://raw.githubusercontent.com/{repo}/{branch}/{file_path}'
    return Config(
        raw_url=raw_url,
        send_only_if_file_changed=bool(behavior.get('send_only_if_file_changed', True)),
        include_header=bool(behavior.get('include_header', True)),
        include_source_link=bool(behavior.get('include_source_link', False)),
        split_long_messages=bool(delivery.get('split_long_messages', True)),
        max_message_length=int(delivery.get('max_message_length', DEFAULT_LIMIT)),
    )


def _fetch_text(url: str) -> str:
    req = Request(url, headers={'User-Agent': 'Hermes-News-Briefings/1.0'})
    with urlopen(req, timeout=30) as resp:
        body = resp.read()
    text = body.decode('utf-8')
    return text


def _parse_date(text: str) -> Optional[str]:
    m = DATE_RE.search(text)
    return m.group(1) if m else None


def _split_message(text: str, limit: int) -> List[str]:
    if len(text) <= limit:
        return [text]
    parts: List[str] = []
    remaining = text
    while len(remaining) > limit:
        cut = remaining.rfind('

', 0, limit)
        if cut <= 0:
            cut = remaining.rfind('
', 0, limit)
        if cut <= 0:
            cut = limit
        parts.append(remaining[:cut].rstrip())
        remaining = remaining[cut:].lstrip()
    if remaining:
        parts.append(remaining)
    return parts


def _state_key(raw_url: str) -> str:
    return hashlib.sha256(raw_url.encode('utf-8')).hexdigest()[:16]


def _load_state() -> Dict[str, Any]:
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text(encoding='utf-8'))
    except Exception:
        return {}


def _save_state(state: Dict[str, Any]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def _send_telegram(token: str, chat_id: str, text: str) -> None:
    payload = json.dumps({
        'chat_id': chat_id,
        'text': text,
        'parse_mode': 'Markdown',
        'disable_web_page_preview': True,
    }).encode('utf-8')
    req = Request(
        f'https://api.telegram.org/bot{token}/sendMessage',
        data=payload,
        headers={'Content-Type': 'application/json'},
    )
    with urlopen(req, timeout=30) as resp:
        resp.read()


def main() -> int:
    parser = argparse.ArgumentParser(description='Fetch latest briefing from GitHub and send it to Telegram.')
    parser.add_argument('--raw-url', default=None, help='Raw GitHub URL for latest/briefing.md')
    parser.add_argument('--dry-run', action='store_true', help='Fetch and validate only, do not send')
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    cfg = _read_config(repo_root, args.raw_url)

    token = os.environ.get('TELEGRAM_BOT_TOKEN', '').strip()
    chat_id = os.environ.get('TELEGRAM_CHAT_ID', '').strip()
    if not token or not chat_id:
        print('Telegram variables are missing: TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are required.', file=sys.stderr)
        return 2

    try:
        text = _fetch_text(cfg.raw_url).strip()
    except HTTPError as e:
        print(f'GitHub fetch failed: HTTP {e.code}', file=sys.stderr)
        return 3
    except URLError as e:
        print(f'GitHub fetch failed: {e.reason}', file=sys.stderr)
        return 3
    except Exception as e:
        print(f'GitHub fetch failed: {e}', file=sys.stderr)
        return 3

    if not text:
        print('Briefing file is empty.', file=sys.stderr)
        return 4

    briefing_date = _parse_date(text)
    if briefing_date is None:
        print('Briefing date is missing or malformed.', file=sys.stderr)
        return 5

    today = datetime.now(timezone.utc).date().isoformat()
    if briefing_date > today:
        print(f'Briefing date is in the future: {briefing_date}.', file=sys.stderr)
        return 6

    digest = hashlib.sha256(text.encode('utf-8')).hexdigest()
    state = _load_state()
    key = _state_key(cfg.raw_url)
    previous = state.get(key, {}) if isinstance(state.get(key, {}), dict) else {}
    if cfg.send_only_if_file_changed and previous.get('digest') == digest:
        print('Briefing unchanged; nothing to send.')
        return 0

    message = text
    if cfg.include_header:
        header = f'

Источник: {cfg.raw_url}' if cfg.include_source_link else ''
        message = text + header

    parts = _split_message(message, cfg.max_message_length) if cfg.split_long_messages else [message]

    if args.dry_run:
        print(f'DRY RUN OK: {len(parts)} part(s), date={briefing_date}')
        return 0

    for part in parts:
        try:
            _send_telegram(token, chat_id, part)
        except HTTPError as e:
            print(f'Telegram send failed: HTTP {e.code}', file=sys.stderr)
            return 7
        except URLError as e:
            print(f'Telegram send failed: {e.reason}', file=sys.stderr)
            return 7
        except Exception as e:
            print(f'Telegram send failed: {e}', file=sys.stderr)
            return 7

    state[key] = {'digest': digest, 'date': briefing_date, 'sent_at': datetime.now(timezone.utc).isoformat()}
    _save_state(state)
    print(f'Sent briefing dated {briefing_date} in {len(parts)} part(s).')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
