from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse
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
        self._proc_log = None

    def get_info(self):
        info = super().get_info()
        can_start, can_stop, can_restart = self._capabilities()
        disabled = bool(getattr(self, "config", {}).get("_disabled", False))
        ops_enabled = bool(getattr(self, "config", {}).get("_ops_enabled", False))
        on_failure = str(getattr(self, "config", {}).get("on_failure") or "alert").lower()
        auto_fix = bool(getattr(self, "config", {}).get("auto_fix", True))
        auto_restart = (on_failure == "restart") and auto_fix
        info["ops_capable"] = bool(can_start or can_stop or can_restart)
        info["start_capable"] = can_start
        info["stop_capable"] = can_stop
        info["restart_capable"] = can_restart
        info["can_start"] = can_start and (not disabled) and ops_enabled
        info["can_stop"] = can_stop and (not disabled) and ops_enabled
        info["can_restart"] = can_restart and (not disabled) and ops_enabled
        info["auto_restart"] = auto_restart
        info["auto_restart_effective"] = auto_restart and can_restart and ops_enabled and (not disabled)
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
        restart_on_running = False
        with self.lock:
            running = self._is_running_nolock()
            if running:
                restart_on_running = bool(self.config.get("start_restart_on_running", False))
                if not restart_on_running:
                    return True, "Already running"
            else:
                restart_on_running = bool(self.config.get("start_restart_on_running", False)) and self._probe_listening_nolock()
        if restart_on_running:
            return self.restart_service()

        with self.lock:
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
                self._close_proc_log_nolock()
                log_path = self._proc_log_path_nolock()
                log_path.parent.mkdir(parents=True, exist_ok=True)
                self._proc_log = open(str(log_path), "ab")
                self._proc = subprocess.Popen(cmd, cwd=self._resolve_cwd(root_dir), stdout=self._proc_log, stderr=self._proc_log)
                self._write_pidfile_nolock(int(self._proc.pid))
                time.sleep(0.2)
                if self._proc.poll() is not None:
                    code = int(self._proc.returncode or 0)
                    self._proc = None
                    self._cleanup_pidfile_nolock()
                    self._close_proc_log_nolock()
                    return False, f"Process exited early: exit_code={code}"
                return True, "Started"
            except Exception as e:
                self._proc = None
                self._cleanup_pidfile_nolock()
                self._close_proc_log_nolock()
                return False, str(e)

    def stop_service(self) -> Tuple[bool, str]:
        with self.lock:
            cmds = self._get_cmds("stop_cmd", "stop_cmds")
            if cmds:
                ok, msg = self._run_local_cmds(cmds)
                if not ok:
                    return ok, msg
                self._cleanup_pidfile_nolock()
                return True, "OK"
            if not self._proc or self._proc.poll() is not None:
                self._proc = None
                pid = self._read_pidfile_nolock()
                if pid is None:
                    return self._stop_by_port_nolock()
                if not self._is_pid_running_nolock(pid):
                    self._cleanup_pidfile_nolock()
                    return self._stop_by_port_nolock()
                ok, msg = self._kill_pid_nolock(pid)
                self._cleanup_pidfile_nolock()
                self._close_proc_log_nolock()
                return ok, msg
            try:
                self._proc.terminate()
                self._proc.wait(timeout=5)
                self._proc = None
                self._cleanup_pidfile_nolock()
                self._close_proc_log_nolock()
                return True, "Stopped"
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
                self._proc = None
                self._cleanup_pidfile_nolock()
                self._close_proc_log_nolock()
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

    def _pidfile_path_nolock(self) -> Path:
        root_dir = Path(__file__).resolve().parents[1]
        return root_dir / "data" / "localproc_pids" / f"{self.service_id}.pid"

    def _proc_log_path_nolock(self) -> Path:
        root_dir = Path(__file__).resolve().parents[1]
        return root_dir / "data" / "logs" / f"localproc_{self.service_id}.log"

    def _close_proc_log_nolock(self) -> None:
        if self._proc_log is None:
            return
        try:
            self._proc_log.close()
        except Exception:
            pass
        self._proc_log = None

    def _probe_listening_nolock(self) -> bool:
        test_api = str(self.config.get("test_api") or "").strip()
        if not test_api:
            return False
        try:
            r = requests.get(test_api, timeout=0.5)
            return bool(r.status_code)
        except Exception:
            return False

    def _stop_by_port_nolock(self) -> Tuple[bool, str]:
        if not bool(self.config.get("start_restart_on_running", False)):
            return True, "Not running"
        port = self._local_port_from_test_api_nolock()
        if port is None:
            return True, "Not running"
        if not self._probe_listening_nolock():
            return True, "Not running"
        ok, msg = self._kill_local_port_listener_nolock(port)
        self._cleanup_pidfile_nolock()
        self._close_proc_log_nolock()
        return ok, msg

    def _local_port_from_test_api_nolock(self) -> Optional[int]:
        v = self.config.get("local_port")
        if v is not None:
            try:
                return int(v)
            except Exception:
                return None
        test_api = str(self.config.get("test_api") or "").strip()
        if not test_api:
            return None
        try:
            u = urlparse(test_api)
            if not u.port:
                return None
            host = str(u.hostname or "").strip().lower()
            if host not in ("127.0.0.1", "localhost", "::1"):
                return None
            return int(u.port)
        except Exception:
            return None

    def _kill_local_port_listener_nolock(self, port: int) -> Tuple[bool, str]:
        try:
            port = int(port)
        except Exception:
            return False, "Invalid port"
        if port <= 0:
            return False, "Invalid port"
        if os.name == "nt":
            try:
                r = subprocess.run(["netstat", "-ano", "-p", "tcp"], capture_output=True, text=True)
                out = (r.stdout or "")
                pids: List[int] = []
                for line in out.splitlines():
                    s = " ".join((line or "").split())
                    if not s:
                        continue
                    if "LISTENING" not in s.upper():
                        continue
                    if f":{port} " not in s and not s.endswith(f":{port}"):
                        continue
                    parts = s.split(" ")
                    if len(parts) < 5:
                        continue
                    try:
                        pid = int(parts[-1])
                    except Exception:
                        continue
                    if pid > 0:
                        pids.append(pid)
                if not pids:
                    return True, "Not running"
                for pid in sorted(set(pids)):
                    subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, text=True)
                return True, f"Stopped (port {port})"
            except Exception as e:
                return False, str(e)
        try:
            r = subprocess.run(["bash", "-lc", f"lsof -ti tcp:{port}"], capture_output=True, text=True)
            pids = [int(x) for x in (r.stdout or "").split() if str(x).strip().isdigit()]
            if not pids:
                return True, "Not running"
            for pid in sorted(set(pids)):
                try:
                    os.kill(pid, 15)
                except Exception:
                    pass
            return True, f"Stopped (port {port})"
        except Exception as e:
            return False, str(e)

    def _read_pidfile_nolock(self) -> Optional[int]:
        path = self._pidfile_path_nolock()
        try:
            if not path.exists():
                return None
            v = (path.read_text(encoding="utf-8") or "").strip()
            if not v:
                return None
            return int(v)
        except Exception:
            return None

    def _write_pidfile_nolock(self, pid: int) -> None:
        path = self._pidfile_path_nolock()
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            path.write_text(str(int(pid)), encoding="utf-8")
        except Exception:
            pass

    def _cleanup_pidfile_nolock(self) -> None:
        path = self._pidfile_path_nolock()
        try:
            if path.exists():
                path.unlink()
        except Exception:
            pass

    def _is_pid_running_nolock(self, pid: int) -> bool:
        try:
            pid = int(pid)
        except Exception:
            return False
        if pid <= 0:
            return False
        if os.name == "nt":
            try:
                r = subprocess.run(["tasklist", "/FI", f"PID eq {pid}"], capture_output=True, text=True)
                out = (r.stdout or "") + "\n" + (r.stderr or "")
                return str(pid) in out
            except Exception:
                return False
        try:
            import signal

            os.kill(pid, 0)
            return True
        except Exception:
            return False

    def _kill_pid_nolock(self, pid: int) -> Tuple[bool, str]:
        try:
            pid = int(pid)
        except Exception:
            return False, "Invalid PID"
        if pid <= 0:
            return False, "Invalid PID"
        if os.name == "nt":
            try:
                r = subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, text=True)
                if r.returncode != 0:
                    return False, ((r.stderr or r.stdout or "").strip() or f"taskkill exit_code={r.returncode}")[:200]
                return True, "Stopped"
            except Exception as e:
                return False, str(e)
        try:
            import signal

            os.kill(pid, signal.SIGTERM)
            return True, "Stopped"
        except Exception as e:
            return False, str(e)

    def _is_running_nolock(self) -> bool:
        if self._proc and self._proc.poll() is None:
            return True
        pid = self._read_pidfile_nolock()
        if pid is None:
            return False
        return self._is_pid_running_nolock(pid)


def _match_expected(response: requests.Response, expected: Any) -> Tuple[bool, str]:
    return match_expected(response, expected)


def create_service(service_id: str, config: Dict[str, Any], config_path: Optional[str] = None) -> BaseService:
    return LocalProcService(service_id, config, config_path=config_path)

