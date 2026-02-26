from __future__ import annotations

import requests


def main() -> int:
    base = "http://127.0.0.1:60005"
    s = requests.Session()
    s.get(base + "/login", timeout=3)
    r = s.post(base + "/login", data={"username": "admin", "password": "admin"}, allow_redirects=False, timeout=3)
    print("login:", r.status_code)
    data = s.get(base + "/api/services?page=1&page_size=50", timeout=3).json()
    for svc in data.get("services") or []:
        print(svc.get("id"), svc.get("status"), svc.get("last_check"), (svc.get("last_error") or "")[:120])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

