import logging
import sys

def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        filename="data/logs/monitor.log",
    )


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

    from core.monitor_engine import MonitorEngine
    from core.service_loader import load_services_from_dir
    from apscheduler.schedulers.background import BackgroundScheduler
    from monitor.webapp import create_app

    services = load_services_from_dir()
    engine = MonitorEngine(services)

    scheduler = BackgroundScheduler()
    scheduler.add_job(func=engine.check_all, trigger="interval", minutes=30)
    scheduler.start()

    engine.check_all()

    app = create_app(engine)
    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)
