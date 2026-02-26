from __future__ import annotations

import os
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

import requests

from core.base_service import BaseService
from core.expected_matcher import match_expected


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
        can_start, can_stop, can_restart = self._capabilities()
        disabled = bool(getattr(self, "config", {}).get("_disabled", False))
        ops_enabled = bool(getattr(self, "config", {}).get("_ops_enabled", False))
        info["ops_capable"] = bool(can_start or can_stop or can_restart)
        info["can_start"] = can_start and (not disabled) and ops_enabled
        info["can_stop"] = can_stop and (not disabled) and ops_enabled
        info["can_restart"] = can_restart and (not disabled) and ops_enabled
        return info

    def check_health(self) -> Tuple[bool, str, Dict[str, Any]]:
        test_api = str(self.config.get("test_api") or "").strip()
        if not test_api:
            return False, "Missing test_api", {"ok": False, "reason": "missing_test_api"}

        expected = self.config.get("expected_response")
        timeout_s = float(self.config.get("timeout_s") or 5)
        method = str(self.config.get("test_method") or "GET").strip().upper()
        payload = self.config.get("test_payload") if isinstance(self.config.get("test_payload"), dict) else None
        max_elapsed_ms = self.config.get("max_elapsed_ms")
        start = time.time()
        try:
            if method == "POST" or payload:
                r = requests.post(test_api, json=(payload or {}), timeout=timeout_s)
            else:
                r = requests.get(test_api, timeout=timeout_s)
            ok, reason = match_expected(r, expected)
            detail = {
                "ok": ok,
                "status_code": r.status_code,
                "elapsed_ms": int((time.time() - start) * 1000),
                "response_excerpt": (r.text or "")[:800],
            }
            if max_elapsed_ms is not None:
                try:
                    if int(detail["elapsed_ms"]) > int(max_elapsed_ms):
                        return False, f"Slow response: {detail['elapsed_ms']}ms", {**detail, "reason": "slow_response"}
                except Exception:
                    pass
            if not ok:
                return False, reason, detail
            return True, "", detail
        except requests.exceptions.Timeout:
            return False, "Timeout", {"ok": False, "reason": "timeout", "elapsed_ms": int((time.time() - start) * 1000)}
        except Exception as e:
            return False, str(e), {"ok": False, "exception": str(e), "elapsed_ms": int((time.time() - start) * 1000)}

    def start_service(self) -> Tuple[bool, str]:
        with self.lock:
            if self._proc and self._proc.poll() is None:
                return True, "Already running"

            cmds = self._get_cmds("start_cmd", "start_cmds")
            if not cmds:
                cmds = self._get_cmds("restart_cmd", "restart_cmds")
            if cmds:
                ok, msg = self._run_local_cmds(cmds)
                if not ok:
                    return ok, msg
                return True, "OK"

            root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
            script = str(self.config.get("local_script") or "").strip()
            if not script:
                return False, "Missing local_script or start_cmds"
            if not os.path.isabs(script):
                script = os.path.join(root_dir, script)
            if not os.path.exists(script):
                return False, f"Script not found: {script}"

            args = self.config.get("local_args") if isinstance(self.config.get("local_args"), list) else []
            cmd = [sys.executable, script] + [str(x) for x in args]
            try:
                self._proc = subprocess.Popen(cmd, cwd=self._resolve_cwd(root_dir), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return True, "Started"
            except Exception as e:
                self._proc = None
                return False, str(e)

    def stop_service(self) -> Tuple[bool, str]:
        with self.lock:
            cmds = self._get_cmds("stop_cmd", "stop_cmds")
            if cmds:
                ok, msg = self._run_local_cmds(cmds)
                if not ok:
                    return ok, msg
                return True, "OK"
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
        with self.lock:
            cmds = self._get_cmds("restart_cmd", "restart_cmds")
            if cmds:
                ok, msg = self._run_local_cmds(cmds)
                if not ok:
                    return ok, msg
                return True, "OK"
        ok, msg = self.stop_service()
        if not ok:
            return ok, msg
        return self.start_service()

    def _capabilities(self) -> Tuple[bool, bool, bool]:
        has_start = bool(self._get_cmds("start_cmd", "start_cmds") or self._get_cmds("restart_cmd", "restart_cmds") or str(self.config.get("local_script") or "").strip())
        has_stop = bool(self._get_cmds("stop_cmd", "stop_cmds") or str(self.config.get("local_script") or "").strip())
        has_restart = bool(self._get_cmds("restart_cmd", "restart_cmds") or has_start)
        return has_start, has_stop, has_restart

    def _get_cmds(self, key_single: str, key_multi: str) -> List[str]:
        if self.config.get(key_multi) and isinstance(self.config.get(key_multi), list):
            return [str(x) for x in self.config.get(key_multi) if str(x).strip()]
        v = str(self.config.get(key_single) or "").strip()
        return [v] if v else []

    def _resolve_cwd(self, root_dir: str) -> str:
        v = str(self.config.get("local_cwd") or "").strip()
        if not v:
            return root_dir
        if os.path.isabs(v):
            return v
        return os.path.abspath(os.path.join(root_dir, v))

    def _run_local_cmds(self, cmds: List[str]) -> Tuple[bool, str]:
        if not cmds:
            return False, "Missing command"
        root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        cwd = self._resolve_cwd(root_dir)
        for cmd in cmds:
            c = str(cmd or "").strip()
            if not c:
                continue
            ignore_error = False
            if c.startswith("@ignore:") or c.startswith("ignore:"):
                ignore_error = True
                c = c.split(":", 1)[1].strip()
            if c.startswith("@script:") or c.startswith("script:"):
                local_path = c.split(":", 1)[1].strip()
                if not os.path.isabs(local_path):
                    local_path = os.path.abspath(os.path.join(root_dir, local_path))
                if not os.path.exists(local_path):
                    return False, f"Script not found: {local_path}"
                if local_path.lower().endswith(".py"):
                    r = subprocess.run([sys.executable, local_path], cwd=cwd, capture_output=True, text=True)
                elif local_path.lower().endswith(".ps1") and os.name == "nt":
                    r = subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", local_path], cwd=cwd, capture_output=True, text=True)
                else:
                    if os.name == "nt":
                        r = subprocess.run(f"\"{local_path}\"", cwd=cwd, shell=True, capture_output=True, text=True)
                    else:
                        r = subprocess.run(["bash", local_path], cwd=cwd, capture_output=True, text=True)
            else:
                r = subprocess.run(c, cwd=cwd, shell=True, capture_output=True, text=True)
            if r.returncode != 0 and not ignore_error:
                err = (r.stderr or r.stdout or "").strip()
                err = err[:600] if err else f"exit_code={r.returncode}"
                return False, err
        return True, "OK"


def _match_expected(response: requests.Response, expected: Any) -> Tuple[bool, str]:
    return match_expected(response, expected)


def create_service(service_id: str, config: Dict[str, Any], config_path: Optional[str] = None) -> BaseService:
    return LocalProcService(service_id, config, config_path=config_path)

