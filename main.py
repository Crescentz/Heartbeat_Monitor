import logging
import os
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
        import apscheduler  # noqa: F401
        import flask  # noqa: F401
        import paramiko  # noqa: F401
        import requests  # noqa: F401
        import yaml  # noqa: F401
    except Exception:
        print("Missing dependencies, run: python -m pip install -r requirements.txt", file=sys.stderr)
        raise


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


def _env_port(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        port = int(str(raw).strip())
    except Exception:
        return default
    if 1 <= port <= 65535:
        return port
    return default


if __name__ == "__main__":
    _import_optional_deps()
    from apscheduler.schedulers.background import BackgroundScheduler

    from core.auto_check_store import get_auto_check_enabled_map, seed_auto_check_enabled, set_auto_check_enabled
    from core.check_schedule import job_id_for_service, parse_check_schedule
    from core.disabled_service_store import get_disabled_map
    from core.failure_policy_store import get_policies
    from core.monitor_engine import MonitorEngine
    from core.ops_mode_store import get_ops_enabled_map, seed_ops_enabled, set_ops_enabled
    from core.runtime_state import (
        apply_runtime_service_flags,
        backfill_bool_store,
        build_initial_auto_check_map,
        build_initial_ops_map,
    )
    from core.schedule_override_store import get_overrides
    from core.service_loader import load_services_from_dir
    from core.storage import ensure_dirs
    from monitor.webapp import create_app

    ensure_dirs()
    _setup_logging()
    log = logging.getLogger("heartbeat_monitor")

    services = load_services_from_dir()
    engine = MonitorEngine(services)
    log.info("Loaded services: %s", len(services))

    scheduler = BackgroundScheduler()
    overrides = get_overrides()
    disabled_map = get_disabled_map()
    initial_ops = build_initial_ops_map(engine.services)
    seed_ops_enabled(sorted(list(engine.services.keys())), default_enabled=False, initial_map=initial_ops)
    ops_enabled_map = backfill_bool_store(get_ops_enabled_map(), initial_ops, set_ops_enabled)
    initial_auto_check = build_initial_auto_check_map(engine.services, overrides)
    seed_auto_check_enabled(sorted(list(engine.services.keys())), default_enabled=False, initial_map=initial_auto_check)
    auto_check_enabled_map = backfill_bool_store(get_auto_check_enabled_map(), initial_auto_check, set_auto_check_enabled)
    failure_policies = get_policies()
    apply_runtime_service_flags(
        engine.services,
        overrides=overrides,
        disabled_map=disabled_map,
        ops_enabled_map=ops_enabled_map,
        auto_check_enabled_map=auto_check_enabled_map,
        failure_policies=failure_policies,
    )
    for service_id, svc in engine.services.items():
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

    engine.scheduler = scheduler
    app = create_app(engine, scheduler=scheduler)
    host = str(os.getenv("HBM_HOST") or "0.0.0.0").strip() or "0.0.0.0"
    port = _env_port("HBM_PORT", 60005)
    debug = _env_flag("HBM_DEBUG", default=False)
    display_host = host if host not in ("0.0.0.0", "::") else "127.0.0.1"
    log.info("Web UI: http://%s:%s/", display_host, port)
    threading.Thread(target=engine.check_all, daemon=True).start()
    app.run(host=host, port=port, debug=debug, use_reloader=False)
