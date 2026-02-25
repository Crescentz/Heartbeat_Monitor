from __future__ import annotations

import secrets
from pathlib import Path


def load_or_create_secret_key() -> str:
    root_dir = Path(__file__).resolve().parents[1]
    path = root_dir / "data" / "secret_key.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    key = secrets.token_hex(32)
    path.write_text(key, encoding="utf-8")
    return key

