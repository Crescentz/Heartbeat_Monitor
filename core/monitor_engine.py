from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional, Tuple

from core.error_log import append_error
from core.event_log import append_event
from core.base_service import BaseService
import time


@dataclass(frozen=True)
class CheckResult:
    ok: bool
    message: str


class MonitorEngine:
    def __init__(self, services: Iterable[BaseService]):
        self._services: Dict[str, BaseService] = {s.service_id: s for s in services}

    @property
    def services(self) -> Dict[str, BaseService]:
        return self._services

    def get(self, service_id: str) -> Optional[BaseService]:
        return self._services.get(service_id)

    def check_one(self, service_id: str, allow_fix: bool = True) -> CheckResult:
        service = self.get(service_id)
        if not service:
            return CheckResult(False, "Service not found")
        if bool(getattr(service, "config", {}).get("_disabled", False)):
            append_event(service.service_id, service.name, "warn", "check", "Disabled")
            return CheckResult(False, "Disabled")
        try:
            ok, msg, detail = service.check_health()
        except Exception as e:
            ok, msg, detail = False, f"check_exception: {type(e).__name__}: {e}", {"exception": str(e), "type": type(e).__name__}
        auto_detail: Dict[str, Any] = {}
        if not ok:
            on_failure = str(service.config.get("on_failure") or "alert").lower()
            ops_enabled = bool(getattr(service, "config", {}).get("_ops_enabled", False))
            if allow_fix and ops_enabled and on_failure == "restart" and bool(service.config.get("auto_fix", True)):
                can_restart = bool(service.get_info().get("can_restart"))
                if can_restart:
                    try:
                        r_ok, r_msg = service.restart_service()
                        auto_detail = {"auto_action": "restart", "auto_ok": r_ok, "auto_message": r_msg}
                    except Exception as e:
                        auto_detail = {
                            "auto_action": "restart",
                            "auto_ok": False,
                            "auto_message": f"restart_exception: {type(e).__name__}: {e}",
                            "exception": str(e),
                            "type": type(e).__name__,
                        }
                else:
                    auto_detail = {"auto_action": "restart", "auto_ok": False, "auto_message": "restart not configured"}
        service.update_status(ok, msg, detail)
        if not ok:
            append_error(service.service_id, service.name, msg)
            if auto_detail.get("auto_action") == "restart":
                append_error(service.service_id, service.name, f"Auto-restart: {auto_detail.get('auto_message')}")
            append_event(service.service_id, service.name, "error", "check", msg or "Unhealthy", detail=detail or {})
            if auto_detail.get("auto_action") == "restart":
                append_event(
                    service.service_id,
                    service.name,
                    "warn" if not bool(auto_detail.get("auto_ok")) else "info",
                    "auto_restart",
                    str(auto_detail.get("auto_message") or ""),
                    detail=auto_detail,
                )
        else:
            append_event(service.service_id, service.name, "info", "check", "Healthy", detail=detail or {})
        return CheckResult(ok, msg or ("Healthy" if ok else "Unhealthy"))

    def check_all(self) -> None:
        for service_id in list(self._services.keys()):
            s = self._services.get(service_id)
            if not s:
                continue
            if bool(getattr(s, "config", {}).get("_disabled", False)):
                continue
            if not bool(s.config.get("auto_check", True)):
                continue
            self.check_one(service_id, allow_fix=True)

    def control(self, service_id: str, action: str, allow_fix: bool = True) -> Tuple[bool, str]:
        service = self.get(service_id)
        if not service:
            return False, "Service not found"
        if bool(getattr(service, "config", {}).get("_disabled", False)):
            append_event(service.service_id, service.name, "warn", action, "Disabled")
            return False, "Disabled"
        if action in ("start", "stop", "restart") and not bool(getattr(service, "config", {}).get("_ops_enabled", False)):
            append_event(service.service_id, service.name, "warn", action, "Ops disabled")
            return False, "Ops disabled"
        if action == "start":
            try:
                ok, msg = service.start_service()
            except Exception as e:
                ok, msg = False, f"start_exception: {type(e).__name__}: {e}"
            append_event(service.service_id, service.name, "info" if ok else "error", "start", msg)
            if ok:
                delay_s = service.config.get("post_control_check_delay_s")
                if delay_s is not None:
                    try:
                        time.sleep(min(float(delay_s), 10.0))
                    except Exception:
                        pass
                r = self.check_one(service_id, allow_fix=False)
                return True, f"{msg}; status={'Healthy' if r.ok else 'Unhealthy'}; {r.message}".strip("; ")
            return ok, msg
        if action == "stop":
            try:
                ok, msg = service.stop_service()
            except Exception as e:
                ok, msg = False, f"stop_exception: {type(e).__name__}: {e}"
            append_event(service.service_id, service.name, "info" if ok else "error", "stop", msg)
            if ok:
                try:
                    service.update_status(False, "Stopped", {"ok": False, "reason": "stopped"})
                except Exception:
                    pass
                return True, msg
            return ok, msg
        if action == "restart":
            try:
                ok, msg = service.restart_service()
            except Exception as e:
                ok, msg = False, f"restart_exception: {type(e).__name__}: {e}"
            append_event(service.service_id, service.name, "info" if ok else "error", "restart", msg)
            if ok:
                delay_s = service.config.get("post_control_check_delay_s")
                if delay_s is not None:
                    try:
                        time.sleep(min(float(delay_s), 10.0))
                    except Exception:
                        pass
                r = self.check_one(service_id, allow_fix=False)
                return True, f"{msg}; status={'Healthy' if r.ok else 'Unhealthy'}; {r.message}".strip("; ")
            return ok, msg
        if action == "check":
            r = self.check_one(service_id, allow_fix=allow_fix)
            append_event(service.service_id, service.name, "info" if r.ok else "error", "check_manual", r.message)
            return True, f"Check complete: {'Healthy' if r.ok else 'Unhealthy'}; {r.message}".strip("; ")
        return False, "Unsupported action"

