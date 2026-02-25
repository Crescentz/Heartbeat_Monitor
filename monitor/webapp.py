from __future__ import annotations

from flask import Flask, jsonify, render_template, request

from core.error_log import query_errors, tail_errors
from core.monitor_engine import MonitorEngine


def create_app(engine: MonitorEngine) -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")

    @app.get("/")
    def index():
        return render_template("index.html", services=[], errors=tail_errors(10))

    @app.get("/api/services")
    def api_services():
        category = str(request.args.get("category") or "").strip().lower()
        on_failure = str(request.args.get("on_failure") or "").strip().lower()
        only_failed = str(request.args.get("only_failed") or "").strip().lower() in ("1", "true", "yes", "on")
        page = int(request.args.get("page") or 1)
        page_size = int(request.args.get("page_size") or 5)

        services = [s.get_info() for s in engine.services.values()]
        services.sort(key=lambda x: str(x.get("id") or ""))

        if category and category != "all":
            services = [s for s in services if str(s.get("category") or "").lower() == category]
        if on_failure and on_failure != "all":
            services = [s for s in services if str(s.get("on_failure") or "").lower() == on_failure]
        if only_failed:
            services = [s for s in services if str(s.get("status") or "") == "Error"]

        total = len(services)
        page = max(page, 1)
        page_size = max(page_size, 1)
        start = (page - 1) * page_size
        end = start + page_size
        items = services[start:end]
        pages = (total + page_size - 1) // page_size if page_size else 1

        return jsonify(
            {
                "services": items,
                "total": total,
                "page": page,
                "page_size": page_size,
                "pages": pages,
            }
        )

    @app.get("/api/errors")
    def api_errors():
        service_id = str(request.args.get("service_id") or "").strip() or None
        retention_days = int(request.args.get("days") or 7)
        page = int(request.args.get("page") or 1)
        page_size = int(request.args.get("page_size") or 10)
        n = request.args.get("n")
        if n is not None:
            items = tail_errors(int(n), retention_days=retention_days)
            return jsonify({"errors": items, "total": len(items), "page": 1, "page_size": len(items), "pages": 1})

        items, total = query_errors(
            service_id=service_id,
            retention_days=retention_days,
            page=page,
            page_size=page_size,
        )
        pages = (total + page_size - 1) // page_size if page_size else 1
        return jsonify({"errors": items, "total": total, "page": page, "page_size": page_size, "pages": pages})

    @app.post("/api/control/<service_id>/<action>")
    def api_control(service_id: str, action: str):
        ok, msg = engine.control(service_id, action)
        return jsonify({"success": ok, "message": msg})

    return app

