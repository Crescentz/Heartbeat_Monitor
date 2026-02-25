from __future__ import annotations

import json
import os
from typing import Dict


DATA_DIR = "data"
FILE_PATH = os.path.join(DATA_DIR, "service_disabled.json")


def get_disabled_map() -> Dict[str, bool]:
    if not os.path.exists(FILE_PATH):
        return {}
    try:
        with open(FILE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            out: Dict[str, bool] = {}
            for k, v in data.items():
                if v:
                    out[str(k)] = True
            return out
    except Exception:
        return {}
    return {}


def is_disabled(service_id: str) -> bool:
    return bool(get_disabled_map().get(str(service_id), False))


def set_disabled(service_id: str, disabled: bool) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    current = get_disabled_map()
    sid = str(service_id)
    if disabled:
        current[sid] = True
    else:
        current.pop(sid, None)
    with open(FILE_PATH, "w", encoding="utf-8") as f:
        json.dump(current, f, ensure_ascii=False, indent=2)

