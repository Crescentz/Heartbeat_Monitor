from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from werkzeug.security import check_password_hash, generate_password_hash


@dataclass(frozen=True)
class User:
    username: str
    role: str


def _users_path() -> Path:
    root_dir = Path(__file__).resolve().parents[1]
    return root_dir / "data" / "users.json"


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {"users": []}
    try:
        return json.loads(path.read_text(encoding="utf-8") or "{}")
    except Exception:
        return {"users": []}


def _write_json_atomic(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def ensure_default_admin() -> bool:
    path = _users_path()
    data = _read_json(path)
    users = data.get("users")
    if not isinstance(users, list):
        users = []
    if any(isinstance(u, dict) and str(u.get("username") or "") == "admin" for u in users):
        return False
    users.append(
        {
            "username": "admin",
            "password_hash": generate_password_hash("admin"),
            "role": "admin",
        }
    )
    data["users"] = users
    _write_json_atomic(path, data)
    return True


def list_users() -> List[User]:
    data = _read_json(_users_path())
    out: List[User] = []
    users = data.get("users")
    if not isinstance(users, list):
        return out
    for u in users:
        if not isinstance(u, dict):
            continue
        username = str(u.get("username") or "").strip()
        role = str(u.get("role") or "user").strip() or "user"
        if username:
            out.append(User(username=username, role=role))
    out.sort(key=lambda x: x.username)
    return out


def get_user(username: str) -> Optional[User]:
    username = str(username or "").strip()
    if not username:
        return None
    for u in list_users():
        if u.username == username:
            return u
    return None


def verify_login(username: str, password: str) -> Optional[User]:
    username = str(username or "").strip()
    password = str(password or "")
    data = _read_json(_users_path())
    users = data.get("users")
    if not isinstance(users, list):
        return None
    for u in users:
        if not isinstance(u, dict):
            continue
        if str(u.get("username") or "").strip() != username:
            continue
        ph = str(u.get("password_hash") or "")
        if not ph:
            return None
        if check_password_hash(ph, password):
            role = str(u.get("role") or "user").strip() or "user"
            return User(username=username, role=role)
        return None
    return None


def create_user(username: str, password: str, role: str = "user") -> Tuple[bool, str]:
    username = str(username or "").strip()
    if not username:
        return False, "missing_username"
    if username.lower() == "admin":
        return False, "reserved_username"
    if len(username) > 64:
        return False, "username_too_long"
    if len(str(password or "")) < 4:
        return False, "password_too_short"
    role = str(role or "user").strip() or "user"
    if role not in ("user", "admin"):
        role = "user"

    path = _users_path()
    data = _read_json(path)
    users = data.get("users")
    if not isinstance(users, list):
        users = []
    if any(isinstance(u, dict) and str(u.get("username") or "") == username for u in users):
        return False, "user_exists"
    users.append({"username": username, "password_hash": generate_password_hash(password), "role": role})
    data["users"] = users
    _write_json_atomic(path, data)
    return True, "ok"


def delete_user(username: str) -> Tuple[bool, str]:
    username = str(username or "").strip()
    if not username:
        return False, "missing_username"
    if username == "admin":
        return False, "cannot_delete_admin"
    path = _users_path()
    data = _read_json(path)
    users = data.get("users")
    if not isinstance(users, list):
        users = []
    kept = [u for u in users if not (isinstance(u, dict) and str(u.get("username") or "") == username)]
    if len(kept) == len(users):
        return False, "user_not_found"
    data["users"] = kept
    _write_json_atomic(path, data)
    return True, "ok"


def set_password(username: str, password: str) -> Tuple[bool, str]:
    username = str(username or "").strip()
    if not username:
        return False, "missing_username"
    if len(str(password or "")) < 4:
        return False, "password_too_short"
    path = _users_path()
    data = _read_json(path)
    users = data.get("users")
    if not isinstance(users, list):
        users = []
    found = False
    for u in users:
        if not isinstance(u, dict):
            continue
        if str(u.get("username") or "") != username:
            continue
        u["password_hash"] = generate_password_hash(password)
        found = True
        break
    if not found:
        return False, "user_not_found"
    data["users"] = users
    _write_json_atomic(path, data)
    return True, "ok"

