from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from core.base_service import BaseService


class InvalidService(BaseService):
    def __init__(self, service_id: str, message: str, config_path: Optional[str] = None):
        super().__init__(
            service_id=service_id,
            name=service_id,
            description="配置加载失败",
            config={},
            config_path=config_path,
        )
        self._message = message
        self.update_status(False, message, {"ok": False, "reason": "invalid_config", "message": message})

    def check_health(self) -> Tuple[bool, str, Dict[str, Any]]:
        return False, self._message, {"ok": False, "reason": "invalid_config", "message": self._message}

    def start_service(self):
        return False, "配置无效，无法启动"

    def stop_service(self):
        return False, "配置无效，无法停止"

    def restart_service(self):
        return False, "配置无效，无法重启"

