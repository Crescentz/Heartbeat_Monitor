from __future__ import annotations

import time

import requests


def main() -> int:
    base = "http://127.0.0.1:5000"
    s = requests.Session()
    s.get(base + "/login", timeout=3)
    r = s.post(base + "/login", data={"username": "admin", "password": "admin"}, allow_redirects=False, timeout=3)
    if r.status_code not in (302, 303):
        raise RuntimeError("login failed")

    sid = "local_test_01"
    r = s.put(base + "/api/admin/disabled", json={"service_id": sid, "disabled": True}, timeout=5)
    try:
        payload = r.json()
    except Exception:
        payload = (r.text or "")[:300]
    print("disable:", r.status_code, payload)

    time.sleep(1)
    services = s.get(base + "/api/services?page=1&page_size=50", timeout=5).json()["services"]
    m = {x["id"]: x for x in services}
    print("status_after_disable:", m[sid]["status"], "disabled=", m[sid].get("disabled"))

    r = s.post(base + f"/api/control/{sid}/check", timeout=5)
    try:
        payload = r.json()
    except Exception:
        payload = (r.text or "")[:300]
    print("check_while_disabled:", r.status_code, payload)

    r = s.put(base + "/api/admin/disabled", json={"service_id": sid, "disabled": False}, timeout=5)
    try:
        payload = r.json()
    except Exception:
        payload = (r.text or "")[:300]
    print("enable:", r.status_code, payload)

    time.sleep(1)
    services = s.get(base + "/api/services?page=1&page_size=50", timeout=5).json()["services"]
    m = {x["id"]: x for x in services}
    print("status_after_enable:", m[sid]["status"], "disabled=", m[sid].get("disabled"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

