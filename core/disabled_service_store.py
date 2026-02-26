from __future__ import annotations

import json
from pathlib import Path
from typing import Dict


def _file_path() -> Path:
    root_dir = Path(__file__).resolve().parents[1]
    return root_dir / "data" / "service_disabled.json"


def get_disabled_map() -> Dict[str, bool]:
    path = _file_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8") or "{}")
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
    path = _file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    current = get_disabled_map()
    sid = str(service_id)
    if disabled:
        current[sid] = True
    else:
        current.pop(sid, None)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)

