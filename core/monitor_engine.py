from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, Tuple

from core.error_log import append_error
from core.base_service import BaseService


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

    def get(self, service_id: str) -> BaseService | None:
        return self._services.get(service_id)

    def check_one(self, service_id: str) -> CheckResult:
        service = self.get(service_id)
        if not service:
            return CheckResult(False, "Service not found")
        ok, msg, detail = service.check_health()
        auto_detail: Dict[str, Any] = {}
        if not ok:
            on_failure = str(service.config.get("on_failure") or "alert").lower()
            if on_failure == "restart" and bool(service.config.get("auto_fix", True)):
                can_restart = bool(service.get_info().get("can_restart"))
                if can_restart:
                    r_ok, r_msg = service.restart_service()
                    auto_detail = {"auto_action": "restart", "auto_ok": r_ok, "auto_message": r_msg}
                else:
                    auto_detail = {"auto_action": "restart", "auto_ok": False, "auto_message": "restart not configured"}
        service.update_status(ok, msg, detail)
        if not ok:
            append_error(service.service_id, service.name, msg)
            if auto_detail.get("auto_action") == "restart":
                append_error(service.service_id, service.name, f"Auto-restart: {auto_detail.get('auto_message')}")
        return CheckResult(ok, msg or ("Healthy" if ok else "Unhealthy"))

    def check_all(self) -> None:
        for service_id in list(self._services.keys()):
            s = self._services.get(service_id)
            if not s:
                continue
            if not bool(s.config.get("auto_check", True)):
                continue
            self.check_one(service_id)

    def control(self, service_id: str, action: str) -> Tuple[bool, str]:
        service = self.get(service_id)
        if not service:
            return False, "Service not found"
        if action == "start":
            return service.start_service()
        if action == "stop":
            return service.stop_service()
        if action == "restart":
            return service.restart_service()
        if action == "check":
            r = self.check_one(service_id)
            return True, f"Check complete: {'Healthy' if r.ok else 'Unhealthy'}; {r.message}".strip("; ")
        return False, "Unsupported action"

