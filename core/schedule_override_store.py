from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional


def _path() -> Path:
    root_dir = Path(__file__).resolve().parents[1]
    return root_dir / "data" / "schedule_overrides.json"


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {"overrides": {}}
    try:
        return json.loads(path.read_text(encoding="utf-8") or "{}")
    except Exception:
        return {"overrides": {}}


def _write_json_atomic(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def get_overrides() -> Dict[str, str]:
    data = _read_json(_path())
    o = data.get("overrides")
    if not isinstance(o, dict):
        return {}
    out: Dict[str, str] = {}
    for sid, v in o.items():
        s = str(v or "").strip()
        if s:
            out[str(sid)] = s
    return out


def get_override(service_id: str) -> Optional[str]:
    return get_overrides().get(str(service_id))


def set_override(service_id: str, check_schedule: str) -> None:
    service_id = str(service_id or "").strip()
    if not service_id:
        return
    check_schedule = str(check_schedule or "").strip()
    path = _path()
    data = _read_json(path)
    o = data.get("overrides")
    if not isinstance(o, dict):
        o = {}
    if check_schedule:
        o[service_id] = check_schedule
    else:
        o.pop(service_id, None)
    data["overrides"] = o
    _write_json_atomic(path, data)

