import logging
import sys
import threading

def _setup_logging() -> None:
    fmt = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    root = logging.getLogger()
    root.setLevel(logging.INFO)

    file_handler = logging.FileHandler("data/logs/monitor.log", encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(fmt)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(fmt)

    root.handlers.clear()
    root.addHandler(file_handler)
    root.addHandler(stream_handler)


def _import_optional_deps() -> None:
    try:
        import flask
        import apscheduler
        import paramiko
        import requests
        import yaml
    except Exception:
        print("缺少依赖，先执行：python -m pip install -r requirements.txt", file=sys.stderr)
        raise

if __name__ == '__main__':
    _import_optional_deps()
    from core.storage import ensure_dirs
    ensure_dirs()
    _setup_logging()
    log = logging.getLogger("heartbeat_monitor")

    from core.check_schedule import job_id_for_service, parse_check_schedule
    from core.auto_check_store import get_auto_check_enabled_map, seed_auto_check_enabled
    from core.disabled_service_store import get_disabled_map
    from core.failure_policy_store import get_policies
    from core.ops_mode_store import get_ops_enabled_map, seed_ops_enabled, set_ops_enabled
    from core.schedule_override_store import get_overrides
    from core.monitor_engine import MonitorEngine
    from core.service_loader import load_services_from_dir
    from apscheduler.schedulers.background import BackgroundScheduler
    from monitor.webapp import create_app

    services = load_services_from_dir()
    engine = MonitorEngine(services)
    log.info("Loaded services: %s", len(services))

    scheduler = BackgroundScheduler()
    overrides = get_overrides()
    disabled_map = get_disabled_map()
    seed_ops_enabled(sorted(list(engine.services.keys())), default_enabled=True)
    ops_enabled_map = get_ops_enabled_map()
    initial_auto_check = {}
    for sid, svc in engine.services.items():
        cfg = getattr(svc, "config", {}) if isinstance(getattr(svc, "config", None), dict) else {}
        sv = str(overrides.get(str(sid)) or "").strip().lower()
        if sv in ("off", "pause", "paused", "disabled", "disable"):
            initial_auto_check[str(sid)] = False
        elif str(sid) in overrides and bool(sv):
            initial_auto_check[str(sid)] = True
        else:
            initial_auto_check[str(sid)] = bool(cfg.get("auto_check", True))
    seed_auto_check_enabled(sorted(list(engine.services.keys())), default_enabled=True, initial_map=initial_auto_check)
    auto_check_enabled_map = get_auto_check_enabled_map()
    failure_policies = get_policies()
    for service_id, svc in engine.services.items():
        if isinstance(getattr(svc, "config", None), dict) and "_base_check_schedule" not in svc.config:
            svc.config["_base_check_schedule"] = str(svc.config.get("check_schedule") or "").strip()
        if isinstance(getattr(svc, "config", None), dict) and disabled_map.get(str(service_id)):
            svc.config["_disabled"] = True
        if isinstance(getattr(svc, "config", None), dict):
            sid = str(service_id)
            if sid not in ops_enabled_map and bool(svc.config.get("ops_default_enabled", False)):
                set_ops_enabled(sid, True)
                ops_enabled_map[sid] = True
            svc.config["_ops_enabled"] = bool(ops_enabled_map.get(sid, False))
            policy = str(failure_policies.get(sid) or "").strip().lower()
            if policy == "alert":
                svc.config["on_failure"] = "alert"
                svc.config["auto_fix"] = False
            elif policy == "restart":
                svc.config["on_failure"] = "restart"
                svc.config["auto_fix"] = True
        if bool(getattr(svc, "config", {}).get("_disabled", False)):
            continue
        schedule_value = str(overrides.get(str(service_id)) or "").strip()
        if schedule_value.lower() in ("off", "pause", "paused", "disabled", "disable"):
            if isinstance(getattr(svc, "config", None), dict):
                svc.config["_auto_check_enabled"] = False
                svc.config["auto_check"] = False
            continue
        enabled = True if (str(service_id) in overrides and bool(schedule_value)) else bool(auto_check_enabled_map.get(str(service_id), False))
        if isinstance(getattr(svc, "config", None), dict):
            svc.config["_auto_check_enabled"] = enabled
            svc.config["auto_check"] = enabled
        if not enabled:
            continue
        schedule_value = overrides.get(str(service_id)) or getattr(svc, "config", {}).get("check_schedule")
        spec = parse_check_schedule(schedule_value, default_minutes=30)
        job_id = job_id_for_service(service_id)
        scheduler.add_job(
            func=engine.check_one,
            trigger=spec.trigger,
            id=job_id,
            args=[service_id],
            max_instances=1,
            coalesce=True,
            misfire_grace_time=60,
            **spec.kwargs,
        )
    scheduler.start()
    log.info("Scheduler started: per-service jobs=%s", len(scheduler.get_jobs()))

    engine.scheduler = scheduler
    app = create_app(engine, scheduler=scheduler)
    log.info("Web UI: http://127.0.0.1:60005/")
    threading.Thread(target=engine.check_all, daemon=True).start()
    app.run(host="0.0.0.0", port=60005, debug=True, use_reloader=False)
