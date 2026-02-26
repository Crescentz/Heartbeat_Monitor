from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional


def _path() -> Path:
    root_dir = Path(__file__).resolve().parents[1]
    return root_dir / "data" / "service_failure_policy.json"


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {"policies": {}}
    try:
        return json.loads(path.read_text(encoding="utf-8") or "{}")
    except Exception:
        return {"policies": {}}


def _write_json_atomic(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def get_policies() -> Dict[str, str]:
    data = _read_json(_path())
    p = data.get("policies")
    if not isinstance(p, dict):
        return {}
    out: Dict[str, str] = {}
    for sid, v in p.items():
        s = str(v or "").strip().lower()
        if s in ("alert", "restart"):
            out[str(sid)] = s
    return out


def get_policy(service_id: str) -> Optional[str]:
    return get_policies().get(str(service_id))


def set_policy(service_id: str, on_failure: str) -> None:
    service_id = str(service_id or "").strip()
    if not service_id:
        return
    on_failure = str(on_failure or "").strip().lower()
    path = _path()
    data = _read_json(path)
    p = data.get("policies")
    if not isinstance(p, dict):
        p = {}
    if on_failure in ("alert", "restart"):
        p[service_id] = on_failure
    else:
        p.pop(service_id, None)
    data["policies"] = p
    _write_json_atomic(path, data)
