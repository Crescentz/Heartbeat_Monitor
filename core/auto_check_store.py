from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional


def _file_path() -> Path:
    root_dir = Path(__file__).resolve().parents[1]
    return root_dir / "data" / "service_auto_check.json"


def _read() -> Dict[str, bool]:
    path = _file_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8") or "{}")
        if isinstance(data, dict):
            out: Dict[str, bool] = {}
            for k, v in data.items():
                out[str(k)] = bool(v)
            return out
    except Exception:
        return {}
    return {}


def get_auto_check_enabled_map() -> Dict[str, bool]:
    return _read()


def is_auto_check_enabled(service_id: str, default: bool = False) -> bool:
    return bool(_read().get(str(service_id), default))


def set_auto_check_enabled(service_id: str, enabled: bool) -> None:
    path = _file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    current = _read()
    current[str(service_id)] = bool(enabled)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def seed_auto_check_enabled(service_ids: List[str], default_enabled: bool = True, initial_map: Optional[Dict[str, bool]] = None) -> None:
    path = _file_path()
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(initial_map, dict):
        data = {str(sid): bool(initial_map.get(str(sid), default_enabled)) for sid in service_ids}
    else:
        data = {str(sid): bool(default_enabled) for sid in service_ids}
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)
