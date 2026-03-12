from __future__ import annotations

from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from apscheduler.schedulers.background import BackgroundScheduler

from core.check_schedule import job_id_for_service, parse_check_schedule
from core.monitor_engine import MonitorEngine
from core.user_store import verify_login
from monitor.webapp import create_app
from services.generic_service import GenericService
from services.localproc_service import LocalProcService


ROOT = Path(__file__).resolve().parents[2]
TARGET_SERVICE_ID = "admin_ops_localproc"
OTHER_SERVICE_ID = "admin_ops_other"
TARGET_PORT = 18121
TEST_USER = "ops_tester"
TEST_PASSWORD = "pass1234"

STATE_FILES = [
    Path("data/users.json"),
    Path("data/service_bindings.json"),
    Path("data/service_auto_check.json"),
    Path("data/service_failure_policy.json"),
    Path("data/service_disabled.json"),
    Path("data/service_ops_mode.json"),
    Path("data/schedule_overrides.json"),
]

ARTIFACT_FILES = [
    Path(f"data/localproc_pids/{TARGET_SERVICE_ID}.pid"),
    Path(f"data/logs/localproc_{TARGET_SERVICE_ID}.log"),
]


class BackupFiles:
    def __init__(self, paths: list[Path]):
        self.paths = paths
        self.backup_dir = ROOT / "data" / "_tmp_admin_common_ops_backup"

    def __enter__(self):
        if self.backup_dir.exists():
            shutil.rmtree(self.backup_dir)
        for rel in self.paths:
            src = ROOT / rel
            dst = self.backup_dir / rel
            if src.exists():
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                src.unlink()
        return self

    def __exit__(self, exc_type, exc, tb):
        for rel in self.paths:
            src = ROOT / rel
            bak = self.backup_dir / rel
            if src.exists():
                src.unlink()
            if bak.exists():
                src.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(bak, src)
        if self.backup_dir.exists():
            shutil.rmtree(self.backup_dir, ignore_errors=True)


def _service_map(client) -> dict[str, dict]:
    resp = client.get("/api/services?page=1&page_size=50")
    assert resp.status_code == 200, resp.data
    payload = resp.get_json()
    return {str(item["id"]): item for item in payload["services"]}


def _json_ok(resp, expected_status: int = 200) -> dict:
    assert resp.status_code == expected_status, resp.data
    data = resp.get_json()
    assert isinstance(data, dict), resp.data
    return data


def _build_engine() -> MonitorEngine:
    fixture_script = ROOT / "archive" / "dev_tools" / "_admin_ops_fixture.py"
    target = LocalProcService(
        TARGET_SERVICE_ID,
        {
            "id": TARGET_SERVICE_ID,
            "name": "Admin Common Ops Fixture",
            "description": "管理员常用操作回归脚本专用样例服务",
            "category": "api",
            "host": "127.0.0.1",
            "plugin": "localproc",
            "test_api": f"http://127.0.0.1:{TARGET_PORT}/health",
            "expected_response": {"ok": True},
            "timeout_s": 2,
            "auto_check": True,
            "check_schedule": "30m",
            "on_failure": "alert",
            "ops_default_enabled": True,
            "local_script": str(fixture_script),
            "local_args": ["--port", str(TARGET_PORT)],
            "start_restart_on_running": True,
            "post_control_check_delay_s": 0.5,
        },
        config_path="archive/dev_tools/_admin_ops_fixture.py",
    )
    other = GenericService(
        OTHER_SERVICE_ID,
        {
            "id": OTHER_SERVICE_ID,
            "name": "Unbound Visibility Probe",
            "description": "用于验证普通用户看不到未绑定服务",
            "category": "api",
            "host": "127.0.0.1",
            "test_api": "http://127.0.0.1:9/health",
            "expected_response": {"ok": True},
            "timeout_s": 1,
            "auto_check": False,
            "check_schedule": "30m",
            "on_failure": "alert",
        },
        config_path="archive/dev_tools/__e2e_admin_common_ops.py",
    )
    return MonitorEngine([target, other])


def _seed_scheduler(engine: MonitorEngine, scheduler: BackgroundScheduler) -> None:
    scheduler.start()
    for sid, svc in engine.services.items():
        if bool(getattr(svc, "config", {}).get("_disabled", False)):
            continue
        if not bool(getattr(svc, "config", {}).get("auto_check", False)):
            continue
        spec = parse_check_schedule(getattr(svc, "config", {}).get("check_schedule"), default_minutes=30)
        scheduler.add_job(
            func=engine.check_one,
            trigger=spec.trigger,
            id=job_id_for_service(sid),
            args=[sid],
            max_instances=1,
            coalesce=True,
            misfire_grace_time=60,
            **spec.kwargs,
        )


def _login(client, username: str, password: str) -> None:
    resp = client.get("/login")
    assert resp.status_code == 200, resp.data
    resp = client.post("/login", data={"username": username, "password": password}, follow_redirects=False)
    assert resp.status_code in (302, 303), resp.data


def main() -> int:
    backup_paths = STATE_FILES + ARTIFACT_FILES
    with BackupFiles(backup_paths):
        engine = _build_engine()
        scheduler = BackgroundScheduler()
        app = create_app(engine, scheduler=scheduler)
        app.testing = True
        _seed_scheduler(engine, scheduler)

        target = engine.services[TARGET_SERVICE_ID]
        try:
            with app.test_client() as admin:
                _login(admin, "admin", "admin")
                assert verify_login("admin", "admin") is not None

                services = _service_map(admin)
                assert TARGET_SERVICE_ID in services
                assert services[TARGET_SERVICE_ID]["ops_enabled"] is True
                assert services[TARGET_SERVICE_ID]["auto_check"] is True
                assert scheduler.get_job(job_id_for_service(TARGET_SERVICE_ID)) is not None

                resp = admin.put("/api/admin/schedules", json={"service_id": TARGET_SERVICE_ID, "check_schedule": "off"})
                _json_ok(resp)
                services = _service_map(admin)
                assert services[TARGET_SERVICE_ID]["auto_check"] is False
                assert scheduler.get_job(job_id_for_service(TARGET_SERVICE_ID)) is None

                resp = admin.put("/api/admin/schedules", json={"service_id": TARGET_SERVICE_ID, "check_schedule": "15m"})
                _json_ok(resp)
                services = _service_map(admin)
                assert services[TARGET_SERVICE_ID]["auto_check"] is True
                assert services[TARGET_SERVICE_ID]["check_schedule"] == "15m"
                assert scheduler.get_job(job_id_for_service(TARGET_SERVICE_ID)) is not None

                resp = admin.put("/api/admin/failure_policy", json={"service_id": TARGET_SERVICE_ID, "auto_restart": True})
                _json_ok(resp)
                services = _service_map(admin)
                assert services[TARGET_SERVICE_ID]["on_failure"] == "restart"
                assert services[TARGET_SERVICE_ID]["auto_restart"] is True
                assert services[TARGET_SERVICE_ID]["auto_restart_effective"] is True

                resp = admin.put("/api/admin/disabled", json={"service_id": TARGET_SERVICE_ID, "disabled": True})
                _json_ok(resp)
                services = _service_map(admin)
                assert services[TARGET_SERVICE_ID]["disabled"] is True
                assert scheduler.get_job(job_id_for_service(TARGET_SERVICE_ID)) is None
                blocked = admin.post(f"/api/control/{TARGET_SERVICE_ID}/check")
                assert blocked.status_code == 400, blocked.data
                assert blocked.get_json()["message"] == "Disabled"

                resp = admin.put("/api/admin/disabled", json={"service_id": TARGET_SERVICE_ID, "disabled": False})
                _json_ok(resp)
                services = _service_map(admin)
                assert services[TARGET_SERVICE_ID]["disabled"] is False
                assert scheduler.get_job(job_id_for_service(TARGET_SERVICE_ID)) is not None

                started = admin.post(f"/api/control/{TARGET_SERVICE_ID}/start")
                payload = _json_ok(started)
                assert payload["success"] is True

                checked = admin.post(f"/api/control/{TARGET_SERVICE_ID}/check")
                payload = _json_ok(checked)
                assert payload["success"] is True

                services = _service_map(admin)
                assert services[TARGET_SERVICE_ID]["status"] == "Running"

                stopped = admin.post(f"/api/control/{TARGET_SERVICE_ID}/stop")
                payload = _json_ok(stopped)
                assert payload["success"] is True

                services = _service_map(admin)
                assert services[TARGET_SERVICE_ID]["status"] in ("Error", "Unknown")

                created = admin.post(
                    "/api/admin/users",
                    json={"username": TEST_USER, "password": TEST_PASSWORD, "role": "user", "can_control": True},
                )
                _json_ok(created)

                bound = admin.put("/api/admin/bindings", json={"service_id": TARGET_SERVICE_ID, "users": [TEST_USER]})
                _json_ok(bound)
                admin.put("/api/admin/bindings", json={"service_id": OTHER_SERVICE_ID, "users": []})

            with app.test_client() as user_client:
                _login(user_client, TEST_USER, TEST_PASSWORD)
                services = _service_map(user_client)
                assert list(services.keys()) == [TARGET_SERVICE_ID]
                me = _json_ok(user_client.get("/api/me"))
                assert me["username"] == TEST_USER
                assert me["can_control"] is True

        finally:
            try:
                target.stop_service()
            except Exception:
                pass
            try:
                scheduler.shutdown(wait=False)
            except Exception:
                pass

    print("admin common ops regression: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
