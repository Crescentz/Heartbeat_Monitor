from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, Optional, Tuple

import requests

from core.base_service import BaseService
from core.ssh_manager import SSHManager


class GenericService(BaseService):
    def __init__(self, service_id: str, config: Dict[str, Any], config_path: Optional[str] = None):
        super().__init__(
            service_id=service_id,
            name=str(config.get("name") or service_id),
            description=str(config.get("description") or ""),
            config=config,
            config_path=config_path,
        )
        host = str(config.get("host") or config.get("ip") or "")
        ssh_port = int(config.get("ssh_port") or 22)
        ssh_user = str(config.get("ssh_user") or config.get("username") or "")
        ssh_password = str(config.get("ssh_password") or config.get("password") or "")
        sudo_password = str(config.get("sudo_password") or "") or None
        private_key = config.get("ssh_private_key")
        private_key_path = config.get("ssh_private_key_path")
        private_key_passphrase = config.get("ssh_private_key_passphrase")
        self.ssh = SSHManager(
            host,
            ssh_port,
            ssh_user,
            ssh_password,
            sudo_password=sudo_password,
            private_key=str(private_key) if private_key else None,
            private_key_path=str(private_key_path) if private_key_path else None,
            private_key_passphrase=str(private_key_passphrase) if private_key_passphrase else None,
        )

    def check_health(self) -> Tuple[bool, str, Dict[str, Any]]:
        test_api = str(self.config.get("test_api") or "").strip()
        if not test_api:
            return False, "Missing test_api", {"ok": False, "reason": "missing_test_api"}

        method = str(self.config.get("test_method") or "").upper().strip()
        test_payload = self.config.get("test_payload")
        expected = self.config.get("expected_response")
        timeout_s = float(self.config.get("timeout_s") or 30)

        start = time.time()
        try:
            if self._has_file_test():
                ok, msg, detail = self._check_file_upload(test_api, expected, timeout_s)
                detail["elapsed_ms"] = int((time.time() - start) * 1000)
                return ok, msg, detail

            if method in ("POST", "PUT", "PATCH") or test_payload is not None:
                r = requests.post(test_api, json=test_payload or {}, timeout=timeout_s)
            else:
                r = requests.get(test_api, timeout=timeout_s)

            ok, reason = self._match_expected(r, expected)
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
        cmds = self._get_cmds("start_cmd", "start_cmds")
        if not cmds:
            cmds = self._get_cmds("restart_cmd", "restart_cmds")
        return self._run_cmds(cmds)

    def stop_service(self) -> Tuple[bool, str]:
        cmds = self._get_cmds("stop_cmd", "stop_cmds")
        return self._run_cmds(cmds)

    def restart_service(self) -> Tuple[bool, str]:
        cmds = self._get_cmds("restart_cmd", "restart_cmds")
        if cmds:
            return self._run_cmds(cmds)
        ok, msg = self.stop_service()
        if not ok:
            return ok, msg
        return self.start_service()

    def _get_cmds(self, key_single: str, key_multi: str) -> list[str]:
        if self.config.get(key_multi) and isinstance(self.config.get(key_multi), list):
            return [str(x) for x in self.config.get(key_multi) if str(x).strip()]
        v = str(self.config.get(key_single) or "").strip()
        return [v] if v else []

    def _run_cmds(self, cmds: list[str]) -> Tuple[bool, str]:
        if not cmds:
            return False, "Missing command"
        sudo = bool(self.config.get("sudo", True))
        wrapper = str(self.config.get("ssh_command_wrapper") or "").strip() or None
        for cmd in cmds:
            out, err = self.ssh.execute_command(cmd, sudo=sudo, wrapper=wrapper)
            if err:
                return False, err
        return True, "OK"

    def _has_file_test(self) -> bool:
        return bool(self.config.get("test_file"))

    def _check_file_upload(self, url: str, expected: Any, timeout_s: float) -> Tuple[bool, str, Dict[str, Any]]:
        local_path = str(self.config.get("test_file") or "").strip()
        if not local_path:
            return False, "Missing test_file", {"ok": False, "reason": "missing_test_file"}
        if not os.path.isabs(local_path):
            local_path = os.path.join(os.getcwd(), local_path)
        if not os.path.exists(local_path):
            return False, f"Test file not found: {local_path}", {"ok": False, "reason": "file_not_found"}

        field = str(self.config.get("file_field") or "file")
        extra = self.config.get("file_extra_form") or {}
        with open(local_path, "rb") as f:
            files = {field: (os.path.basename(local_path), f, "application/pdf")}
            r = requests.post(url, files=files, data=extra, timeout=timeout_s)
        ok, reason = self._match_expected(r, expected)
        detail = {
            "ok": ok,
            "status_code": r.status_code,
            "response_excerpt": (r.text or "")[:800],
            "file": os.path.basename(local_path),
        }
        if not ok:
            return False, reason, detail
        return True, "", detail

    def _match_expected(self, response: requests.Response, expected: Any) -> Tuple[bool, str]:
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


def _json_dumps(x: Any) -> str:
    try:
        return json.dumps(x, ensure_ascii=False)
    except Exception:
        return str(x)

