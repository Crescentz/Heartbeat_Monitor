from __future__ import annotations

from pathlib import Path

from flask import Flask, jsonify, redirect, render_template, request, session, url_for

from core.app_secrets import load_or_create_secret_key
from core.acl_store import allowed_service_ids, get_bindings, set_service_users
from core.check_schedule import job_id_for_service, parse_check_schedule
from core.schedule_override_store import get_overrides, set_override
from core.disabled_service_store import get_disabled_map, set_disabled
from core.user_store import create_user, delete_user, ensure_default_admin, list_users, set_password, verify_login
from core.error_log import query_errors, tail_errors
from core.event_log import query_events, tail_events
from core.monitor_engine import MonitorEngine


def create_app(engine: MonitorEngine, scheduler=None) -> Flask:
    root_dir = Path(__file__).resolve().parents[1]
    app = Flask(
        __name__,
        template_folder=str(root_dir / "templates"),
        static_folder=str(root_dir / "static"),
    )
    app.secret_key = load_or_create_secret_key()
    app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax")
    created_admin = ensure_default_admin()
    disabled_map = get_disabled_map()
    for sid, svc in engine.services.items():
        if isinstance(getattr(svc, "config", None), dict) and disabled_map.get(str(sid)):
            svc.config["_disabled"] = True

    def _current_user() -> tuple[str, str]:
        return str(session.get("username") or ""), str(session.get("role") or "user")

    def _is_admin() -> bool:
        return str(session.get("role") or "") == "admin"

    @app.get("/")
    def index():
        username, role = _current_user()
        allowed = set(allowed_service_ids(username, role, list(engine.services.keys())))
        errors = [e for e in tail_errors(10) if str(e.get("service_id") or "") in allowed] if role != "admin" else tail_errors(10)
        return render_template("index.html", services=[], errors=errors, user={"username": username, "role": role})

    @app.get("/login")
    def login():
        if session.get("username"):
            return redirect(url_for("index"))
        return render_template("login.html", created_admin=created_admin)

    @app.post("/login")
    def do_login():
        username = str(request.form.get("username") or "").strip()
        password = str(request.form.get("password") or "")
        user = verify_login(username, password)
        if not user:
            return render_template("login.html", created_admin=False, error="账号或密码错误")
        session["username"] = user.username
        session["role"] = user.role
        return redirect(url_for("index"))

    @app.get("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))

    @app.before_request
    def require_login():
        endpoint = request.endpoint or ""
        if endpoint.startswith("static"):
            return None
        if endpoint in ("login", "do_login"):
            return None
        if session.get("username"):
            return None
        if request.path.startswith("/api/"):
            return jsonify({"error": "unauthorized"}), 401
        return redirect(url_for("login"))

    @app.after_request
    def disable_cache(resp):
        if request.path in ("/", "/login") or request.path.startswith("/api/"):
            resp.headers["Cache-Control"] = "no-store"
        return resp

    @app.get("/api/me")
    def api_me():
        username, role = _current_user()
        return jsonify({"username": username, "role": role})

    @app.put("/api/me/password")
    def api_me_password():
        username, _ = _current_user()
        payload = request.get_json(silent=True) or {}
        ok, msg = set_password(username, payload.get("password"))
        return jsonify({"success": ok, "message": msg}), (200 if ok else 400)

    @app.get("/api/admin/users")
    def api_admin_users():
        if not _is_admin():
            return jsonify({"error": "forbidden"}), 403
        return jsonify({"users": [{"username": u.username, "role": u.role} for u in list_users()]})

    @app.post("/api/admin/users")
    def api_admin_create_user():
        if not _is_admin():
            return jsonify({"error": "forbidden"}), 403
        payload = request.get_json(silent=True) or {}
        ok, msg = create_user(payload.get("username"), payload.get("password"), payload.get("role") or "user")
        return jsonify({"success": ok, "message": msg}), (200 if ok else 400)

    @app.delete("/api/admin/users/<username>")
    def api_admin_delete_user(username: str):
        if not _is_admin():
            return jsonify({"error": "forbidden"}), 403
        ok, msg = delete_user(username)
        return jsonify({"success": ok, "message": msg}), (200 if ok else 400)

    @app.put("/api/admin/users/<username>/password")
    def api_admin_set_password(username: str):
        if not _is_admin():
            return jsonify({"error": "forbidden"}), 403
        payload = request.get_json(silent=True) or {}
        ok, msg = set_password(username, payload.get("password"))
        return jsonify({"success": ok, "message": msg}), (200 if ok else 400)

    @app.get("/api/admin/bindings")
    def api_admin_bindings():
        if not _is_admin():
            return jsonify({"error": "forbidden"}), 403
        return jsonify(
            {
                "bindings": get_bindings(),
                "services": sorted(list(engine.services.keys())),
                "users": [u.username for u in list_users()],
            }
        )

    @app.put("/api/admin/bindings")
    def api_admin_set_binding():
        if not _is_admin():
            return jsonify({"error": "forbidden"}), 403
        payload = request.get_json(silent=True) or {}
        sid = str(payload.get("service_id") or "").strip()
        users = payload.get("users") if isinstance(payload.get("users"), list) else []
        set_service_users(sid, [str(x) for x in users])
        return jsonify({"success": True, "message": "ok"})

    @app.get("/api/admin/schedules")
    def api_admin_schedules():
        if not _is_admin():
            return jsonify({"error": "forbidden"}), 403
        base: dict[str, str] = {}
        for sid, svc in engine.services.items():
            base[str(sid)] = str(getattr(svc, "config", {}).get("check_schedule") or "").strip()
        return jsonify({"overrides": get_overrides(), "base": base})

    @app.put("/api/admin/schedules")
    def api_admin_set_schedule():
        if not _is_admin():
            return jsonify({"error": "forbidden"}), 403
        payload = request.get_json(silent=True) or {}
        sid = str(payload.get("service_id") or "").strip()
        schedule_str = str(payload.get("check_schedule") or "").strip()
        if sid not in engine.services:
            return jsonify({"success": False, "message": "service_not_found"}), 400

        svc = engine.services[sid]
        base_key = "_base_check_schedule"
        if isinstance(getattr(svc, "config", None), dict) and base_key not in svc.config:
            svc.config[base_key] = str(svc.config.get("check_schedule") or "").strip()

        if schedule_str:
            parse_check_schedule(schedule_str, default_minutes=30)
            set_override(sid, schedule_str)
            if isinstance(getattr(svc, "config", None), dict):
                svc.config["check_schedule"] = schedule_str
        else:
            set_override(sid, "")
            if isinstance(getattr(svc, "config", None), dict):
                svc.config["check_schedule"] = str(svc.config.get(base_key) or "").strip()

        if scheduler is not None and bool(getattr(svc, "config", {}).get("auto_check", True)):
            job_id = job_id_for_service(sid)
            try:
                scheduler.remove_job(job_id)
            except Exception:
                pass
            spec = parse_check_schedule(
                get_overrides().get(sid) or getattr(svc, "config", {}).get("check_schedule"),
                default_minutes=30,
            )
            scheduler.add_job(
                func=engine.check_one,
                trigger=spec.trigger,
                id=job_id,
                args=[sid],
                max_instances=1,
                coalesce=True,
                misfire_grace_time=60,
                **spec.kwargs,
            )

        return jsonify({"success": True, "message": "ok"})

    @app.get("/api/admin/disabled")
    def api_admin_disabled():
        if not _is_admin():
            return jsonify({"error": "forbidden"}), 403
        return jsonify({"disabled": get_disabled_map(), "services": sorted(list(engine.services.keys()))})

    @app.put("/api/admin/disabled")
    def api_admin_set_disabled():
        if not _is_admin():
            return jsonify({"error": "forbidden"}), 403
        payload = request.get_json(silent=True) or {}
        sid = str(payload.get("service_id") or "").strip()
        disabled = bool(payload.get("disabled"))
        if sid not in engine.services:
            return jsonify({"success": False, "message": "service_not_found"}), 400

        set_disabled(sid, disabled)
        svc = engine.services[sid]
        if isinstance(getattr(svc, "config", None), dict):
            svc.config["_disabled"] = disabled

        if scheduler is not None:
            job_id = job_id_for_service(sid)
            try:
                scheduler.remove_job(job_id)
            except Exception:
                pass
            if (not disabled) and bool(getattr(svc, "config", {}).get("auto_check", True)):
                overrides = get_overrides()
                schedule_value = overrides.get(str(sid)) or getattr(svc, "config", {}).get("check_schedule")
                spec = parse_check_schedule(schedule_value, default_minutes=30)
                scheduler.add_job(
                    func=engine.check_one,
                    trigger=spec.trigger,
                    id=job_id,
                    args=[sid],
                    max_instances=1,
                    coalesce=True,
                    misfire_grace_time=60,
                    **spec.kwargs,
                )
        return jsonify({"success": True, "message": "ok"})

    @app.get("/api/services")
    def api_services():
        username, role = _current_user()
        allowed = set(allowed_service_ids(username, role, list(engine.services.keys())))
        category = str(request.args.get("category") or "").strip().lower()
        on_failure = str(request.args.get("on_failure") or "").strip().lower()
        only_failed = str(request.args.get("only_failed") or "").strip().lower() in ("1", "true", "yes", "on")
        page = int(request.args.get("page") or 1)
        page_size = int(request.args.get("page_size") or 5)

        overrides = get_overrides()
        services = [s.get_info() for s in engine.services.values()]
        services.sort(key=lambda x: str(x.get("id") or ""))
        if role != "admin":
            services = [s for s in services if str(s.get("id") or "") in allowed]
        for s in services:
            sid = str(s.get("id") or "")
            if sid in overrides:
                s["check_schedule"] = overrides[sid]

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
        username, role = _current_user()
        allowed = set(allowed_service_ids(username, role, list(engine.services.keys())))
        service_id = str(request.args.get("service_id") or "").strip() or None
        retention_days = int(request.args.get("days") or 7)
        page = int(request.args.get("page") or 1)
        page_size = int(request.args.get("page_size") or 10)
        n = request.args.get("n")
        if n is not None:
            items = tail_errors(int(n), retention_days=retention_days)
            if role != "admin":
                items = [e for e in items if str(e.get("service_id") or "") in allowed]
            return jsonify({"errors": items, "total": len(items), "page": 1, "page_size": len(items), "pages": 1})

        if role != "admin" and service_id and service_id not in allowed:
            return jsonify({"error": "forbidden"}), 403

        if role != "admin" and not service_id:
            all_items, _ = query_errors(
                service_id=None,
                retention_days=retention_days,
                page=1,
                page_size=1000000,
            )
            all_items = [e for e in all_items if str(e.get("service_id") or "") in allowed]
            total = len(all_items)
            page = max(page, 1)
            page_size = max(page_size, 1)
            start = (page - 1) * page_size
            end = start + page_size
            items = all_items[start:end]
        else:
            items, total = query_errors(
                service_id=service_id,
                retention_days=retention_days,
                page=page,
                page_size=page_size,
            )
        pages = (total + page_size - 1) // page_size if page_size else 1
        return jsonify({"errors": items, "total": total, "page": page, "page_size": page_size, "pages": pages})

    @app.get("/api/events")
    def api_events():
        username, role = _current_user()
        allowed = set(allowed_service_ids(username, role, list(engine.services.keys())))
        service_id = str(request.args.get("service_id") or "").strip() or None
        retention_days = int(request.args.get("days") or 7)
        page = int(request.args.get("page") or 1)
        page_size = int(request.args.get("page_size") or 30)
        n = request.args.get("n")
        if n is not None:
            items = tail_events(int(n), retention_days=retention_days)
            if role != "admin":
                items = [e for e in items if str(e.get("service_id") or "") in allowed]
            return jsonify({"events": items, "total": len(items), "page": 1, "page_size": len(items), "pages": 1})

        if role != "admin" and service_id and service_id not in allowed:
            return jsonify({"error": "forbidden"}), 403

        if role != "admin" and not service_id:
            all_items, _ = query_events(
                service_id=None,
                retention_days=retention_days,
                page=1,
                page_size=1000000,
            )
            all_items = [e for e in all_items if str(e.get("service_id") or "") in allowed]
            total = len(all_items)
            page = max(page, 1)
            page_size = max(page_size, 1)
            start = (page - 1) * page_size
            end = start + page_size
            items = all_items[start:end]
        else:
            items, total = query_events(
                service_id=service_id,
                retention_days=retention_days,
                page=page,
                page_size=page_size,
            )
        pages = (total + page_size - 1) // page_size if page_size else 1
        return jsonify({"events": items, "total": total, "page": page, "page_size": page_size, "pages": pages})

    @app.post("/api/control/<service_id>/<action>")
    def api_control(service_id: str, action: str):
        username, role = _current_user()
        allowed = set(allowed_service_ids(username, role, list(engine.services.keys())))
        if role != "admin" and service_id not in allowed:
            return jsonify({"success": False, "message": "forbidden"}), 403
        ok, msg = engine.control(service_id, action)
        return jsonify({"success": ok, "message": msg})

    return app

