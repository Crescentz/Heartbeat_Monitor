from __future__ import annotations

from pathlib import Path
from typing import Dict

from flask import Flask, jsonify, redirect, render_template, request, session, url_for

from core.app_secrets import load_or_create_secret_key
from core.acl_store import allowed_service_ids, get_bindings, set_service_users
from core.auto_check_store import get_auto_check_enabled_map, seed_auto_check_enabled, set_auto_check_enabled
from core.check_schedule import job_id_for_service, parse_check_schedule
from core.failure_policy_store import get_policies, set_policy
from core.schedule_override_store import get_overrides, set_override
from core.disabled_service_store import get_disabled_map, set_disabled
from core.ops_mode_store import get_ops_enabled_map, seed_ops_enabled, set_ops_enabled
from core.user_store import create_user, delete_user, ensure_default_admin, get_user, list_users, set_can_control, set_password, verify_login
from core.error_log import query_errors, tail_errors
from core.event_log import query_events, tail_events
from core.monitor_engine import MonitorEngine
from core.app_info import APP_INFO


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
    seed_ops_enabled(sorted(list(engine.services.keys())), default_enabled=True)
    ops_enabled_map = get_ops_enabled_map()
    overrides = get_overrides()
    initial_auto_check = {}
    for sid, svc in engine.services.items():
        cfg = getattr(svc, "config", {}) if isinstance(getattr(svc, "config", None), dict) else {}
        sv = str(overrides.get(str(sid)) or "").strip().lower()
        if sv in ("off", "pause", "paused", "disabled", "disable"):
            initial_auto_check[str(sid)] = False
        else:
            initial_auto_check[str(sid)] = bool(cfg.get("auto_check", False))
    seed_auto_check_enabled(sorted(list(engine.services.keys())), default_enabled=False, initial_map=initial_auto_check)
    auto_check_enabled_map = get_auto_check_enabled_map()
    failure_policies = get_policies()
    for sid, svc in engine.services.items():
        if isinstance(getattr(svc, "config", None), dict) and disabled_map.get(str(sid)):
            svc.config["_disabled"] = True
        if isinstance(getattr(svc, "config", None), dict):
            svc.config["_ops_enabled"] = bool(ops_enabled_map.get(str(sid), False))
            policy = str(failure_policies.get(str(sid)) or "").strip().lower()
            if policy == "alert":
                svc.config["on_failure"] = "alert"
                svc.config["auto_fix"] = False
            elif policy == "restart":
                svc.config["on_failure"] = "restart"
                svc.config["auto_fix"] = True

            sv = str(overrides.get(str(sid)) or "").strip()
            if sv.lower() in ("off", "pause", "paused", "disabled", "disable"):
                svc.config["_auto_check_enabled"] = False
                svc.config["auto_check"] = False
            else:
                enabled = bool(auto_check_enabled_map.get(str(sid), False))
                svc.config["_auto_check_enabled"] = enabled
                svc.config["auto_check"] = enabled

    def _current_user() -> tuple[str, str, bool]:
        username = str(session.get("username") or "")
        role = str(session.get("role") or "user")
        if role == "admin":
            return username, role, True
        u = get_user(username) if username else None
        return username, role, bool(getattr(u, "can_control", False)) if u else False

    def _is_admin() -> bool:
        return str(session.get("role") or "") == "admin"

    def _parse_int_arg(name: str, default: int, minimum: int, maximum: int) -> int:
        """
        安全解析整数查询参数。
        用户传入非法值时回退默认值，并做上下界约束，避免触发 500。
        """
        raw = request.args.get(name)
        if raw is None:
            return default
        try:
            val = int(str(raw).strip())
        except Exception:
            return default
        return min(max(val, minimum), maximum)

    def _mark_for_action_state(state: str) -> str:
        s = str(state or "").strip().lower()
        if s == "ok":
            return "√"
        if s == "partial":
            return "-"
        return "x"

    def _action_state_for_service(info: dict, action: str, user_can_control: bool) -> str:
        """
        计算服务动作三态：
        - ok: 当前可执行（√）
        - partial: 当前动作缺少 YAML 命令/脚本（-）
        - blocked: 其余不可执行场景（x）
        """
        _ = user_can_control  # 当前三态主要表达动作配置与可执行结果，保留参数以兼容调用处
        a = str(action or "").strip().lower()
        disabled = bool(info.get("disabled"))
        if a == "check":
            return "blocked" if disabled else "ok"

        if disabled:
            return "blocked"

        # start/stop/restart：只要该动作没配置命令/脚本，都统一显示为 "-"
        # 让用户第一眼区分“配置缺失(-)”和“不可执行(x)”。
        if not bool(info.get(f"{a}_capable")):
            return "partial"

        if bool(info.get(f"can_{a}")):
            return "ok"
        return "blocked"

    @app.get("/")
    def index():
        username, role, can_control = _current_user()
        allowed = set(allowed_service_ids(username, role, list(engine.services.keys())))
        errors = [e for e in tail_errors(10) if str(e.get("service_id") or "") in allowed] if role != "admin" else tail_errors(10)
        return render_template(
            "index.html",
            services=[],
            errors=errors,
            user={"username": username, "role": role, "can_control": can_control},
            app_info=APP_INFO,
        )

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
        username, role, can_control = _current_user()
        return jsonify({"username": username, "role": role, "can_control": can_control})

    @app.put("/api/me/password")
    def api_me_password():
        username, _, _ = _current_user()
        payload = request.get_json(silent=True) or {}
        ok, msg = set_password(username, payload.get("password"))
        return jsonify({"success": ok, "message": msg}), (200 if ok else 400)

    @app.get("/api/admin/users")
    def api_admin_users():
        if not _is_admin():
            return jsonify({"error": "forbidden"}), 403
        return jsonify(
            {"users": [{"username": u.username, "role": u.role, "can_control": bool(getattr(u, "can_control", False))} for u in list_users()]}
        )

    @app.post("/api/admin/users")
    def api_admin_create_user():
        if not _is_admin():
            return jsonify({"error": "forbidden"}), 403
        payload = request.get_json(silent=True) or {}
        ok, msg = create_user(
            payload.get("username"),
            payload.get("password"),
            payload.get("role") or "user",
            can_control=bool(payload.get("can_control")) if "can_control" in payload else None,
        )
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

    @app.put("/api/admin/users/<username>/control")
    def api_admin_set_user_control(username: str):
        if not _is_admin():
            return jsonify({"error": "forbidden"}), 403
        payload = request.get_json(silent=True) or {}
        ok, msg = set_can_control(username, bool(payload.get("can_control")))
        return jsonify({"success": ok, "message": msg}), (200 if ok else 400)

    @app.get("/api/admin/ops_mode")
    def api_admin_ops_mode():
        if not _is_admin():
            return jsonify({"error": "forbidden"}), 403
        return jsonify({"ops_enabled": get_ops_enabled_map(), "services": sorted(list(engine.services.keys()))})

    @app.put("/api/admin/ops_mode")
    def api_admin_set_ops_mode():
        if not _is_admin():
            return jsonify({"error": "forbidden"}), 403
        payload = request.get_json(silent=True) or {}
        sid = str(payload.get("service_id") or "").strip()
        enabled = bool(payload.get("ops_enabled"))
        if sid not in engine.services:
            return jsonify({"success": False, "message": "service_not_found"}), 400
        set_ops_enabled(sid, enabled)
        svc = engine.services[sid]
        if isinstance(getattr(svc, "config", None), dict):
            svc.config["_ops_enabled"] = enabled
        return jsonify({"success": True, "message": "ok"})

    @app.post("/api/admin/ops_mode/bulk")
    def api_admin_set_ops_mode_bulk():
        if not _is_admin():
            return jsonify({"error": "forbidden"}), 403
        payload = request.get_json(silent=True) or {}
        mode = str(payload.get("mode") or "").strip().lower()
        if mode not in ("enable_all", "disable_all", "enable_capable"):
            return jsonify({"success": False, "message": "invalid_mode"}), 400

        changed = 0
        for sid, svc in engine.services.items():
            info = {}
            try:
                info = svc.get_info() or {}
            except Exception:
                info = {}
            ops_capable = bool(info.get("ops_capable"))
            if mode == "enable_capable" and not ops_capable:
                enabled = False
            else:
                enabled = (mode != "disable_all")
            set_ops_enabled(sid, enabled)
            if isinstance(getattr(svc, "config", None), dict):
                svc.config["_ops_enabled"] = enabled
            changed += 1
        return jsonify({"success": True, "message": "ok", "changed": changed})

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
        if sid not in engine.services:
            return jsonify({"success": False, "message": "service_not_found"}), 400
        users = payload.get("users") if isinstance(payload.get("users"), list) else []
        set_service_users(sid, [str(x) for x in users])
        return jsonify({"success": True, "message": "ok"})

    @app.get("/api/admin/schedules")
    def api_admin_schedules():
        if not _is_admin():
            return jsonify({"error": "forbidden"}), 403
        auto_map = get_auto_check_enabled_map()
        overrides = get_overrides()
        base: Dict[str, str] = {}
        enabled: Dict[str, bool] = {}
        for sid, svc in engine.services.items():
            cfg = getattr(svc, "config", {}) if isinstance(getattr(svc, "config", None), dict) else {}
            base[str(sid)] = str(cfg.get("_base_check_schedule") or cfg.get("check_schedule") or "").strip()
            sv = str(overrides.get(str(sid)) or "").strip()
            if sv.lower() in ("off", "pause", "paused", "disabled", "disable"):
                enabled[str(sid)] = False
            else:
                enabled[str(sid)] = bool(auto_map.get(str(sid), False))
        return jsonify({"overrides": overrides, "base": base, "enabled": enabled})

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

        if schedule_str and schedule_str.lower() in ("off", "pause", "paused", "disabled", "disable"):
            set_override(sid, "off")
            if isinstance(getattr(svc, "config", None), dict):
                set_auto_check_enabled(sid, False)
                svc.config["_auto_check_enabled"] = False
                svc.config["auto_check"] = False
            if scheduler is not None:
                job_id = job_id_for_service(sid)
                try:
                    scheduler.remove_job(job_id)
                except Exception:
                    pass
            return jsonify({"success": True, "message": "ok"})

        if schedule_str:
            try:
                parse_check_schedule(schedule_str, default_minutes=30, strict=True)
            except Exception:
                return jsonify({"success": False, "message": "invalid_check_schedule"}), 400
            set_override(sid, schedule_str)
            if isinstance(getattr(svc, "config", None), dict):
                set_auto_check_enabled(sid, True)
                svc.config["check_schedule"] = schedule_str
                svc.config["_auto_check_enabled"] = True
                svc.config["auto_check"] = True
        else:
            set_override(sid, "")
            if isinstance(getattr(svc, "config", None), dict):
                set_auto_check_enabled(sid, True)
                svc.config["check_schedule"] = str(svc.config.get(base_key) or "").strip()
                svc.config["_auto_check_enabled"] = True
                svc.config["auto_check"] = True

        if scheduler is not None:
            job_id = job_id_for_service(sid)
            try:
                scheduler.remove_job(job_id)
            except Exception:
                pass
            if not bool(getattr(svc, "config", {}).get("_disabled", False)):
                overrides_now = get_overrides()
                v = str(overrides_now.get(sid) or "").strip()
                enabled_now = bool(get_auto_check_enabled_map().get(sid, False))
                if v.lower() in ("off", "pause", "paused", "disabled", "disable"):
                    enabled_now = False
                if enabled_now:
                    spec = parse_check_schedule(
                        overrides_now.get(sid) or getattr(svc, "config", {}).get("check_schedule"),
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

    @app.put("/api/admin/failure_policy")
    def api_admin_set_failure_policy():
        if not _is_admin():
            return jsonify({"error": "forbidden"}), 403
        payload = request.get_json(silent=True) or {}
        sid = str(payload.get("service_id") or "").strip()
        auto_restart = bool(payload.get("auto_restart"))
        if sid not in engine.services:
            return jsonify({"success": False, "message": "service_not_found"}), 400
        mode = "restart" if auto_restart else "alert"
        set_policy(sid, mode)
        svc = engine.services[sid]
        if isinstance(getattr(svc, "config", None), dict):
            svc.config["on_failure"] = mode
            svc.config["auto_fix"] = True if mode == "restart" else False
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
        username, role, can_control = _current_user()
        allowed = set(allowed_service_ids(username, role, list(engine.services.keys())))
        user_can_control = (role == "admin") or bool(can_control)
        q = str(request.args.get("q") or "").strip().lower()
        category = str(request.args.get("category") or "").strip().lower()
        on_failure = str(request.args.get("on_failure") or "").strip().lower()
        status = str(request.args.get("status") or "").strip().lower()
        only_failed = str(request.args.get("only_failed") or "").strip().lower() in ("1", "true", "yes", "on")
        page = _parse_int_arg("page", default=1, minimum=1, maximum=1000000)
        page_size = _parse_int_arg("page_size", default=5, minimum=1, maximum=200)

        overrides = get_overrides()
        auto_map = get_auto_check_enabled_map()
        failure_policies = get_policies()
        services = [s.get_info() for s in engine.services.values()]
        services.sort(key=lambda x: str(x.get("id") or ""))
        if role != "admin":
            services = [s for s in services if str(s.get("id") or "") in allowed]
            if not can_control:
                for s in services:
                    s["can_start"] = False
                    s["can_stop"] = False
                    s["can_restart"] = False
        for s in services:
            sid = str(s.get("id") or "")
            v = str(overrides.get(sid) or "").strip()
            if sid in overrides and v:
                s["check_schedule"] = v
            if v.lower() in ("off", "pause", "paused", "disabled", "disable"):
                s["auto_check"] = False
            else:
                s["auto_check"] = bool(auto_map.get(sid, False))

            pol = str(failure_policies.get(sid) or "").strip().lower()
            if pol in ("alert", "restart"):
                s["on_failure"] = pol
                s["auto_restart"] = True if pol == "restart" else False
            s["auto_restart_effective"] = bool(s.get("auto_restart")) and bool(s.get("restart_capable")) and bool(s.get("ops_enabled")) and (not bool(s.get("disabled")))

            for action in ("start", "stop", "restart", "check"):
                state = _action_state_for_service(s, action, user_can_control=user_can_control)
                s[f"action_state_{action}"] = state
                s[f"action_mark_{action}"] = _mark_for_action_state(state)

        if q:
            def _hit(x: dict) -> bool:
                return any(
                    q in str(x.get(k) or "").lower()
                    for k in ("id", "name", "host", "test_api", "description", "category")
                )
            services = [s for s in services if _hit(s)]
        if category and category != "all":
            services = [s for s in services if str(s.get("category") or "").lower() == category]
        if on_failure and on_failure != "all":
            services = [s for s in services if str(s.get("on_failure") or "").lower() == on_failure]
        if status and status != "all":
            mapping = {"running": "Running", "error": "Error", "disabled": "Disabled", "unknown": "Unknown"}
            want = mapping.get(status, status)
            services = [s for s in services if str(s.get("status") or "") == want]
        if only_failed:
            services = [s for s in services if str(s.get("status") or "") == "Error"]

        total = len(services)
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
        username, role, _ = _current_user()
        allowed = set(allowed_service_ids(username, role, list(engine.services.keys())))
        service_id = str(request.args.get("service_id") or "").strip() or None
        retention_days = _parse_int_arg("days", default=7, minimum=1, maximum=90)
        page = _parse_int_arg("page", default=1, minimum=1, maximum=1000000)
        page_size = _parse_int_arg("page_size", default=10, minimum=1, maximum=200)
        n = request.args.get("n")
        if n is not None:
            try:
                nn = min(max(int(str(n).strip()), 1), 200)
            except Exception:
                nn = 10
            items = tail_errors(nn, retention_days=retention_days)
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
                page_size=2000,
            )
            all_items = [e for e in all_items if str(e.get("service_id") or "") in allowed]
            total = len(all_items)
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
        username, role, _ = _current_user()
        allowed = set(allowed_service_ids(username, role, list(engine.services.keys())))
        service_id = str(request.args.get("service_id") or "").strip() or None
        retention_days = _parse_int_arg("days", default=7, minimum=1, maximum=90)
        page = _parse_int_arg("page", default=1, minimum=1, maximum=1000000)
        page_size = _parse_int_arg("page_size", default=30, minimum=1, maximum=200)
        n = request.args.get("n")
        if n is not None:
            try:
                nn = min(max(int(str(n).strip()), 1), 500)
            except Exception:
                nn = 30
            items = tail_events(nn, retention_days=retention_days)
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
                page_size=5000,
            )
            all_items = [e for e in all_items if str(e.get("service_id") or "") in allowed]
            total = len(all_items)
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
        action = str(action or "").strip().lower()
        username, role, can_control = _current_user()
        allowed = set(allowed_service_ids(username, role, list(engine.services.keys())))
        if role != "admin" and service_id not in allowed:
            return jsonify({"success": False, "message": "forbidden"}), 403
        if action not in ("start", "stop", "restart", "check"):
            return jsonify({"success": False, "message": "unsupported_action"}), 400
        if action in ("start", "stop", "restart") and role != "admin" and not can_control:
            return jsonify({"success": False, "message": "control_not_authorized"}), 403
        allow_fix = True if role == "admin" or can_control else False
        ok, msg = engine.control(service_id, action, allow_fix=allow_fix)
        if not ok and msg == "Service not found":
            return jsonify({"success": False, "message": "service_not_found"}), 404
        return jsonify({"success": ok, "message": msg}), (200 if ok else 400)

    return app

