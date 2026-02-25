from __future__ import annotations

import requests


def main() -> int:
    base = "http://127.0.0.1:5000"
    s = requests.Session()
    s.get(base + "/login", timeout=3)
    r = s.post(base + "/login", data={"username": "admin", "password": "admin"}, allow_redirects=False, timeout=3)
    print("login:", r.status_code, "set-cookie" in {k.lower() for k in r.headers.keys()})

    for path, method in [
        ("/api/me", "GET"),
        ("/api/admin/users", "GET"),
        ("/api/admin/schedules", "GET"),
        ("/api/admin/disabled", "GET"),
    ]:
        resp = s.request(method, base + path, timeout=5)
        print(method, path, resp.status_code, (resp.headers.get("Content-Type") or ""), (resp.text or "")[:120].replace("\n", " "))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

