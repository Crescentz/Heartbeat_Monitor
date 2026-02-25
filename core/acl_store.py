from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


def _bindings_path() -> Path:
    root_dir = Path(__file__).resolve().parents[1]
    return root_dir / "data" / "service_bindings.json"


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {"bindings": {}}
    try:
        return json.loads(path.read_text(encoding="utf-8") or "{}")
    except Exception:
        return {"bindings": {}}


def _write_json_atomic(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def get_bindings() -> Dict[str, List[str]]:
    data = _read_json(_bindings_path())
    b = data.get("bindings")
    if not isinstance(b, dict):
        return {}
    out: Dict[str, List[str]] = {}
    for sid, users in b.items():
        if not isinstance(users, list):
            continue
        out[str(sid)] = [str(x) for x in users if str(x).strip()]
    return out


def set_service_users(service_id: str, usernames: List[str]) -> None:
    service_id = str(service_id or "").strip()
    if not service_id:
        return
    norm = sorted({str(x).strip() for x in (usernames or []) if str(x).strip()})
    path = _bindings_path()
    data = _read_json(path)
    b = data.get("bindings")
    if not isinstance(b, dict):
        b = {}
    b[service_id] = norm
    data["bindings"] = b
    _write_json_atomic(path, data)


def allowed_service_ids(username: str, role: str, all_service_ids: List[str]) -> List[str]:
    role = str(role or "user").strip() or "user"
    if role == "admin":
        return list(all_service_ids)
    username = str(username or "").strip()
    if not username:
        return []
    bindings = get_bindings()
    allowed: List[str] = []
    for sid in all_service_ids:
        users = bindings.get(sid) or []
        if username in users:
            allowed.append(sid)
    return allowed

