from __future__ import annotations

import time
from pathlib import Path
import sys

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core.event_log import query_events
from core.monitor_engine import MonitorEngine
from core.service_loader import load_services_from_dir


def main() -> int:
    services = load_services_from_dir()
    engine = MonitorEngine(services)

    sid = "local_restart_demo"
    svc = engine.get(sid)
    if not svc:
        raise RuntimeError("service_not_found: local_restart_demo")

    if isinstance(getattr(svc, "config", None), dict):
        svc.config["_disabled"] = False
        svc.config["_ops_enabled"] = True
        svc.config["on_failure"] = "restart"
        svc.config["auto_fix"] = True
        svc.config["post_auto_restart_check_delay_s"] = 1

    ok, msg = engine.control(sid, "start", allow_fix=False)
    if not ok:
        raise RuntimeError(f"start failed: {msg}")

    time.sleep(0.5)
    requests.post("http://127.0.0.1:18081/toggle", json={"ok": False}, timeout=3)

    r = engine.check_one(sid, allow_fix=True)
    print("check_one:", r.ok, r.message)

    time.sleep(0.2)
    items, _ = query_events(service_id=sid, limit=30, page=1, page_size=30, retention_days=1)
    actions = [str(x.get("action") or "") for x in items]
    print("actions_tail:", actions[:12])
    need = {"auto_restart", "restart_wait", "check_after_restart"}
    if not need.issubset(set(actions)):
        raise RuntimeError(f"missing events: {need - set(actions)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
