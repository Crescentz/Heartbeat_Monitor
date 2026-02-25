import logging
import sys

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
    from core.disabled_service_store import get_disabled_map
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
    for service_id, svc in engine.services.items():
        if isinstance(getattr(svc, "config", None), dict) and "_base_check_schedule" not in svc.config:
            svc.config["_base_check_schedule"] = str(svc.config.get("check_schedule") or "").strip()
        if isinstance(getattr(svc, "config", None), dict) and disabled_map.get(str(service_id)):
            svc.config["_disabled"] = True
        if bool(getattr(svc, "config", {}).get("_disabled", False)):
            continue
        if not bool(getattr(svc, "config", {}).get("auto_check", True)):
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

    engine.check_all()

    engine.scheduler = scheduler
    app = create_app(engine, scheduler=scheduler)
    log.info("Web UI: http://127.0.0.1:5000/")
    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)
