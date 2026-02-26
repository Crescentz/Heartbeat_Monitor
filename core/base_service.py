from abc import ABC, abstractmethod
from datetime import datetime
import threading
from typing import Any, Dict, List, Optional

class BaseService(ABC):
    def __init__(self, service_id, name, description, config, config_path: Optional[str] = None):
        self.service_id = service_id
        self.name = name
        self.description = description
        self.config = config
        self.config_path = config_path
        self.status = "Unknown"
        self.last_check = None
        self.last_error = ""
        self.last_test_detail: Dict[str, Any] = {}
        self.uptime_start = None
        self.failure_count = 0
        self.total_checks = 0
        self.lock = threading.Lock()

    def update_status(self, is_healthy: bool, error_msg: str = "", detail: Optional[Dict[str, Any]] = None):
        with self.lock:
            self.total_checks += 1
            self.last_check = datetime.now()
            if detail is not None:
                self.last_test_detail = detail
            
            if is_healthy:
                self.status = "Running"
                self.last_error = ""
                if self.uptime_start is None:
                    self.uptime_start = datetime.now()
            else:
                self.status = "Error"
                self.last_error = error_msg
                self.failure_count += 1
                self.uptime_start = None

    def get_info(self):
        uptime_str = "0s"
        if self.uptime_start:
            delta = datetime.now() - self.uptime_start
            uptime_str = str(delta).split('.')[0]
            
        failure_rate = 0
        if self.total_checks > 0:
            failure_rate = round((self.failure_count / self.total_checks) * 100, 2)

        config = self.config if isinstance(self.config, dict) else {}
        start_cmds = config.get("start_cmds")
        stop_cmds = config.get("stop_cmds")
        restart_cmds = config.get("restart_cmds")
        has_start = bool(config.get("start_cmd") or (isinstance(start_cmds, list) and len(start_cmds) > 0))
        has_stop = bool(config.get("stop_cmd") or (isinstance(stop_cmds, list) and len(stop_cmds) > 0))
        has_restart = bool(config.get("restart_cmd") or (isinstance(restart_cmds, list) and len(restart_cmds) > 0))
        ops_capable = has_start or has_stop or has_restart

        category = str(config.get("category") or config.get("service_type") or "api").lower()
        auto_check = bool(config.get("_auto_check_enabled", config.get("auto_check", True)))
        on_failure = str(config.get("on_failure") or "alert").lower()
        auto_restart = (on_failure == "restart") and bool(config.get("auto_fix", True))
        check_schedule = str(config.get("check_schedule") or "").strip()
        base_check_schedule = str(config.get("_base_check_schedule") or "").strip()
        disabled = bool(config.get("_disabled", False))
        ops_enabled = bool(config.get("_ops_enabled", False))
        ops_doc = config.get("ops_doc")

        def _collect_cmds(single_key: str, multi_key: str) -> List[str]:
            if isinstance(config.get(multi_key), list):
                return [str(x) for x in config.get(multi_key) if str(x).strip()]
            v = str(config.get(single_key) or "").strip()
            return [v] if v else []

        return {
            "id": self.service_id,
            "name": self.name,
            "description": self.description,
            "status": "Disabled" if disabled else self.status,
            "last_check": self.last_check.strftime("%Y-%m-%d %H:%M:%S") if self.last_check else "Never",
            "last_error": self.last_error,
            "uptime": uptime_str,
            "failure_rate": f"{failure_rate}%",
            "category": category,
            "auto_check": auto_check,
            "on_failure": on_failure,
            "auto_restart": auto_restart,
            "check_schedule": check_schedule,
            "base_check_schedule": base_check_schedule,
            "disabled": disabled,
            "ops_enabled": ops_enabled,
            "ops_capable": ops_capable,
            "can_start": has_start and (not disabled) and ops_enabled,
            "can_stop": has_stop and (not disabled) and ops_enabled,
            "can_restart": has_restart and (not disabled) and ops_enabled,
            "start_capable": has_start,
            "stop_capable": has_stop,
            "restart_capable": has_restart,
            "host": config.get("host") or config.get("ip") or "N/A",
            "test_api": config.get("test_api") or "",
            "config_path": self.config_path or "",
            "last_test_detail": self.last_test_detail,
            "ops_doc": ops_doc,
            "start_cmds": _collect_cmds("start_cmd", "start_cmds"),
            "stop_cmds": _collect_cmds("stop_cmd", "stop_cmds"),
            "restart_cmds": _collect_cmds("restart_cmd", "restart_cmds"),
        }

    # ===== 扩展点@服务接口：新增服务必须实现以下 3 个操作与健康检测 =====
    @abstractmethod
    def check_health(self):
        """
        Returns: (bool, str, dict) -> (ok, message, detail)
        """
        pass

    # ===== 扩展点@服务接口 =====
    @abstractmethod
    def start_service(self):
        pass

    # ===== 扩展点@服务接口 =====
    @abstractmethod
    def stop_service(self):
        pass
    
    # ===== 扩展点@服务接口 =====
    @abstractmethod
    def restart_service(self):
        pass
