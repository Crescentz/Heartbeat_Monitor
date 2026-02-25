from core.base_service import BaseService
from core.ssh_manager import SSHManager
import requests
import logging
import os
import time
from typing import Any, Dict, Optional, Tuple

class MineruService(BaseService):
    def __init__(self, service_id: str, config: Dict[str, Any], config_path: Optional[str] = None):
        super().__init__(
            service_id=service_id, 
            name=str(config.get("name") or "Mineru"),
            description=str(config.get("description") or ""),
            config=config,
            config_path=config_path,
        )
        host = str(config.get("host") or config.get("ip") or "")
        private_key = config.get("ssh_private_key")
        private_key_path = config.get("ssh_private_key_path")
        private_key_passphrase = config.get("ssh_private_key_passphrase")
        self.ssh = SSHManager(
            host,
            int(config.get("ssh_port") or 22),
            str(config.get("ssh_user") or config.get("username") or ""),
            str(config.get("ssh_password") or config.get("password") or ""),
            sudo_password=str(config.get("sudo_password") or "") or None,
            private_key=str(private_key) if private_key else None,
            private_key_path=str(private_key_path) if private_key_path else None,
            private_key_passphrase=str(private_key_passphrase) if private_key_passphrase else None,
        )
        self.container_name = str(config.get("container_name") or "mineru_container")
        
        self.test_pdf_path = str(config.get("test_file") or os.path.join("data", "test.pdf"))

    def check_health(self) -> Tuple[bool, str, Dict[str, Any]]:
        test_api = str(self.config.get("test_api") or "").strip()
        if not test_api:
            return False, "Missing test_api", {"ok": False, "reason": "missing_test_api"}

        if not os.path.exists(self.test_pdf_path):
            return False, f"Test file not found: {self.test_pdf_path}", {"ok": False, "reason": "file_not_found"}

        try:
            field = str(self.config.get("file_field") or "file")
            expected = self.config.get("expected_response")
            timeout_s = float(self.config.get("timeout_s") or 60)

            start = time.time()
            with open(self.test_pdf_path, "rb") as f:
                files = {field: (os.path.basename(self.test_pdf_path), f, "application/pdf")}
                r = requests.post(test_api, files=files, timeout=timeout_s)

            ok, reason = self._match_expected(r, expected)
            detail = {
                "ok": ok,
                "status_code": r.status_code,
                "elapsed_ms": int((time.time() - start) * 1000),
                "response_excerpt": (r.text or "")[:800],
                "file": os.path.basename(self.test_pdf_path),
            }
            if not ok:
                return False, reason, detail
            return True, "", detail

        except Exception as e:
            return False, str(e), {"ok": False, "exception": str(e)}

    def start_service(self):
        cmds = self._get_cmds("start_cmd", "start_cmds")
        if cmds:
            return self._run_cmds(cmds)
        
        logging.info("Starting Mineru Service...")
        out, err = self.ssh.execute_command(f"sudo docker inspect -f '{{{{.State.Running}}}}' {self.container_name}", sudo=True)
        
        container_running = False
        if out and "true" in out.lower():
            container_running = True
        elif "No such object" in err or "Error" in err:
            # Container doesn't exist, create it
            run_cmd = (
                f"sudo docker run --gpus all --shm-size 32g "
                f"-p 30000:30000 -p 7860:7860 -p {self.config['port']}:8000 "
                f"--ipc=host -itd --name {self.container_name} "
                f"-e MINERU_MODEL_SOURCE=local "
                f"mineru:latest /bin/bash"
            )
            out, err = self.ssh.execute_command(run_cmd, sudo=True)
            if err and "Conflict" not in err:
                return False, f"Docker run failed: {err}"
            container_running = True
            time.sleep(5) # Wait for container init

        if not container_running:
            # Start existing stopped container
            out, err = self.ssh.execute_command(f"sudo docker start {self.container_name}", sudo=True)
            if err: return False, f"Docker start failed: {err}"
            time.sleep(3)

        internal_cmd = str(self.config.get("api_start_cmd") or "nohup mineru-api --host 0.0.0.0 --port 8000 > /vllm-workspace/api.log 2>&1 &")
        full_exec_cmd = f"sudo docker exec -d {self.container_name} bash -c '{internal_cmd}'"
        
        out, err = self.ssh.execute_command(full_exec_cmd, sudo=True)
        if err:
            return False, f"Internal API start failed: {err}"
            
        return True, "Service started command sent"

    def stop_service(self):
        cmds = self._get_cmds("stop_cmd", "stop_cmds")
        if cmds:
            return self._run_cmds(cmds)
        out, err = self.ssh.execute_command(f"sudo docker stop {self.container_name}", sudo=True)
        if err:
            return False, err
        return True, "Container stopped"

    def restart_service(self):
        cmds = self._get_cmds("restart_cmd", "restart_cmds")
        if cmds:
            return self._run_cmds(cmds)
        self.stop_service()
        time.sleep(5)
        return self.start_service()

    def _get_cmds(self, key_single: str, key_multi: str) -> list[str]:
        if self.config.get(key_multi) and isinstance(self.config.get(key_multi), list):
            return [str(x) for x in self.config.get(key_multi) if str(x).strip()]
        v = str(self.config.get(key_single) or "").strip()
        return [v] if v else []

    def _run_cmds(self, cmds: list[str]):
        if not cmds:
            return False, "Missing command"
        wrapper = str(self.config.get("ssh_command_wrapper") or "").strip() or None
        for cmd in cmds:
            out, err = self.ssh.execute_command(cmd, sudo=True, wrapper=wrapper)
            if err:
                return False, err
        return True, "OK"

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


def create_service(service_id: str, cfg: Dict[str, Any], config_path: str) -> MineruService:
    return MineruService(service_id, cfg, config_path=config_path)
