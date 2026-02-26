from __future__ import annotations

import requests


def main() -> int:
    base = "http://127.0.0.1:60005"
    s = requests.Session()
    s.get(base + "/login", timeout=3)
    r = s.post(base + "/login", data={"username": "admin", "password": "admin"}, allow_redirects=False, timeout=3)
    if r.status_code not in (302, 303):
        raise RuntimeError(f"login failed: {r.status_code} {r.text[:200]}")

    sid = "local_restart_demo"
    for auto_restart in (False, True):
        resp = s.put(base + "/api/admin/failure_policy", json={"service_id": sid, "auto_restart": auto_restart}, timeout=5)
        if resp.status_code != 200:
            raise RuntimeError(f"set failure_policy failed: {resp.status_code} {resp.text[:200]}")

        services = s.get(base + "/api/services?page=1&page_size=50", timeout=5).json()["services"]
        svc = [x for x in services if x.get("id") == sid][0]
        print("set auto_restart=", auto_restart, "-> on_failure=", svc.get("on_failure"), "auto_restart=", svc.get("auto_restart"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
