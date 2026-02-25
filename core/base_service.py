from abc import ABC, abstractmethod
from datetime import datetime
import threading
from typing import Any, Dict, Optional

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

        start_cmds = self.config.get("start_cmds") if isinstance(self.config, dict) else None
        stop_cmds = self.config.get("stop_cmds") if isinstance(self.config, dict) else None
        restart_cmds = self.config.get("restart_cmds") if isinstance(self.config, dict) else None
        has_start = bool(self.config.get("start_cmd") or (isinstance(start_cmds, list) and len(start_cmds) > 0))
        has_stop = bool(self.config.get("stop_cmd") or (isinstance(stop_cmds, list) and len(stop_cmds) > 0))
        has_restart = bool(self.config.get("restart_cmd") or (isinstance(restart_cmds, list) and len(restart_cmds) > 0))

        category = str(self.config.get("category") or self.config.get("service_type") or "api").lower()
        auto_check = bool(self.config.get("auto_check", True))
        on_failure = str(self.config.get("on_failure") or "alert").lower()

        return {
            "id": self.service_id,
            "name": self.name,
            "description": self.description,
            "status": self.status,
            "last_check": self.last_check.strftime("%Y-%m-%d %H:%M:%S") if self.last_check else "Never",
            "last_error": self.last_error,
            "uptime": uptime_str,
            "failure_rate": f"{failure_rate}%",
            "category": category,
            "auto_check": auto_check,
            "on_failure": on_failure,
            "can_start": has_start,
            "can_stop": has_stop,
            "can_restart": has_restart,
            "host": self.config.get("host") or self.config.get("ip") or "N/A",
            "test_api": self.config.get("test_api") or "",
            "config_path": self.config_path or "",
            "last_test_detail": self.last_test_detail,
        }

    @abstractmethod
    def check_health(self):
        """
        Returns: (bool, str, dict) -> (ok, message, detail)
        """
        pass

    @abstractmethod
    def start_service(self):
        pass

    @abstractmethod
    def stop_service(self):
        pass
    
    @abstractmethod
    def restart_service(self):
        pass
