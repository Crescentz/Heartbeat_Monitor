from __future__ import annotations

import os
import subprocess
import sys
import time
from typing import Any, Dict, Optional, Tuple

import requests

from core.base_service import BaseService


class LocalProcService(BaseService):
    def __init__(self, service_id: str, config: Dict[str, Any], config_path: Optional[str] = None):
        super().__init__(
            service_id=service_id,
            name=str(config.get("name") or service_id),
            description=str(config.get("description") or ""),
            config=config,
            config_path=config_path,
        )
        self._proc: Optional[subprocess.Popen] = None

    def get_info(self):
        info = super().get_info()
        info["can_start"] = True
        info["can_stop"] = True
        info["can_restart"] = True
        return info

    def check_health(self) -> Tuple[bool, str, Dict[str, Any]]:
        test_api = str(self.config.get("test_api") or "").strip()
        if not test_api:
            return False, "Missing test_api", {"ok": False, "reason": "missing_test_api"}

        expected = self.config.get("expected_response")
        timeout_s = float(self.config.get("timeout_s") or 5)
        start = time.time()
        try:
            r = requests.get(test_api, timeout=timeout_s)
            ok, reason = _match_expected(r, expected)
            detail = {
                "ok": ok,
                "status_code": r.status_code,
                "elapsed_ms": int((time.time() - start) * 1000),
                "response_excerpt": (r.text or "")[:800],
            }
            if not ok:
                return False, reason, detail
            return True, "", detail
        except Exception as e:
            return False, str(e), {"ok": False, "exception": str(e), "elapsed_ms": int((time.time() - start) * 1000)}

    def start_service(self) -> Tuple[bool, str]:
        with self.lock:
            if self._proc and self._proc.poll() is None:
                return True, "Already running"

            root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
            script = str(self.config.get("local_script") or "").strip()
            if not script:
                return False, "Missing local_script"
            if not os.path.isabs(script):
                script = os.path.join(root_dir, script)
            if not os.path.exists(script):
                return False, f"Script not found: {script}"

            args = self.config.get("local_args") if isinstance(self.config.get("local_args"), list) else []
            cmd = [sys.executable, script] + [str(x) for x in args]
            try:
                self._proc = subprocess.Popen(cmd, cwd=root_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return True, "Started"
            except Exception as e:
                self._proc = None
                return False, str(e)

    def stop_service(self) -> Tuple[bool, str]:
        with self.lock:
            if not self._proc or self._proc.poll() is not None:
                self._proc = None
                return True, "Not running"
            try:
                self._proc.terminate()
                self._proc.wait(timeout=5)
                self._proc = None
                return True, "Stopped"
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
                self._proc = None
                return True, "Killed"

    def restart_service(self) -> Tuple[bool, str]:
        ok, msg = self.stop_service()
        if not ok:
            return ok, msg
        return self.start_service()


def _match_expected(response: requests.Response, expected: Any) -> Tuple[bool, str]:
    if response.status_code >= 500:
        return False, f"HTTP {response.status_code}"
    if expected is None:
        return (200 <= response.status_code < 300), f"HTTP {response.status_code}"
    if isinstance(expected, dict):
        try:
            body = response.json()
        except Exception:
            return False, "Response is not JSON"
        for k, v in expected.items():
            if body.get(k) != v:
                return False, f"Expected {k}={v}"
        return True, ""
    if isinstance(expected, str):
        if expected in (response.text or ""):
            return True, ""
        return False, f"Expected substring not found: {expected}"
    return True, ""


def create_service(service_id: str, config: Dict[str, Any], config_path: Optional[str] = None) -> BaseService:
    return LocalProcService(service_id, config, config_path=config_path)

