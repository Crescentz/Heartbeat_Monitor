from __future__ import annotations

import time
from pathlib import Path
import sys

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core.monitor_engine import MonitorEngine
from core.service_loader import load_services_from_dir


def main() -> int:
    engine = MonitorEngine(load_services_from_dir())
    sid = "local_restart_demo"
    svc = engine.get(sid)
    if not svc:
        raise RuntimeError("service_not_found")
    if isinstance(getattr(svc, "config", None), dict):
        svc.config["_disabled"] = False
        svc.config["_ops_enabled"] = True

    ok, msg = engine.control(sid, "start", allow_fix=False)
    if not ok:
        raise RuntimeError(f"start failed: {msg}")

    time.sleep(0.5)
    requests.post("http://127.0.0.1:18081/toggle", json={"ok": False}, timeout=3)
    time.sleep(0.2)

    ok, msg = engine.control(sid, "start", allow_fix=False)
    print("start again:", ok, msg)
    if "Healthy" not in msg:
        raise RuntimeError("expected healthy after start on running")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
