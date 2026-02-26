from __future__ import annotations

from core.monitor_engine import MonitorEngine
from core.service_loader import load_services_from_dir
from monitor.webapp import create_app


def main() -> int:
    services = load_services_from_dir()
    engine = MonitorEngine(services)
    app = create_app(engine, scheduler=None)
    app.testing = True
    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess["username"] = "admin"
            sess["role"] = "admin"

        r = c.get("/api/admin/disabled")
        assert r.status_code == 200, r.data

        sid = next(iter(engine.services.keys()))
        r = c.put("/api/admin/disabled", json={"service_id": sid, "disabled": True})
        assert r.status_code == 200, r.data
        assert bool(engine.services[sid].config.get("_disabled")) is True

        r = c.put("/api/admin/disabled", json={"service_id": sid, "disabled": False})
        assert r.status_code == 200, r.data
        assert bool(engine.services[sid].config.get("_disabled")) is False
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

