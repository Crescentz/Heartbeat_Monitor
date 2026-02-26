from __future__ import annotations

import time

import requests


def main() -> int:
    base = "http://127.0.0.1:60005"
    s = requests.Session()

    s.get(base + "/login", timeout=3)
    r = s.post(base + "/login", data={"username": "admin", "password": "admin"}, allow_redirects=False, timeout=3)
    if r.status_code not in (302, 303):
        raise RuntimeError(f"login failed: {r.status_code} {r.text[:200]}")

    services = s.get(base + "/api/services?page=1&page_size=20", timeout=3).json()["services"]
    print("services:", [x.get("id") for x in services])

    r = s.post(base + "/api/control/local_restart_demo/start", timeout=10).json()
    print("start:", r)

    time.sleep(1)
    r = s.post(base + "/api/control/local_restart_demo/check", timeout=10).json()
    print("check:", r)

    events = s.get(base + "/api/events?n=10&days=7", timeout=3).json()["events"]
    print("events_tail:", [(e.get("action"), e.get("level"), e.get("message")) for e in events[:5]])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

