from core.base_service import BaseService
from core.ssh_manager import SSHManager
import requests
import logging
import os
import time
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.expected_matcher import match_expected

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
        self.sudo = bool(config.get("sudo", True))
        
        self.test_pdf_path = str(config.get("test_file") or os.path.join("data", "test.pdf"))

    def check_health(self) -> Tuple[bool, str, Dict[str, Any]]:
        test_api = str(self.config.get("test_api") or "").strip()
        if not test_api:
            return False, "Missing test_api", {"ok": False, "reason": "missing_test_api"}

        test_file_path = self.test_pdf_path
        if not os.path.isabs(test_file_path):
            test_file_path = os.path.join(os.getcwd(), test_file_path)
        if not os.path.exists(test_file_path):
            return False, f"Test file not found: {test_file_path}", {"ok": False, "reason": "file_not_found"}

        try:
            field = str(self.config.get("file_field") or "files")
            field_as_list = self.config.get("file_field_as_list")
            if field_as_list is None:
                field_as_list = (field == "files")
            expected = self.config.get("expected_response")
            timeout_s = float(self.config.get("timeout_s") or 60)
            max_elapsed_ms = self.config.get("max_elapsed_ms")
            extra_form = self.config.get("file_extra_form") or {}

            start = time.time()
            with open(test_file_path, "rb") as f:
                filename = os.path.basename(test_file_path)
                if field_as_list:
                    files = [(field, (filename, f, "application/pdf"))]
                else:
                    files = {field: (filename, f, "application/pdf")}

                data = self._normalize_multipart_form(extra_form)
                r = requests.post(test_api, files=files, data=data, timeout=timeout_s)

            ok, reason = match_expected(r, expected)
            detail = {
                "ok": ok,
                "status_code": r.status_code,
                "elapsed_ms": int((time.time() - start) * 1000),
                "response_excerpt": (r.text or "")[:800],
                "file": filename,
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
            return False, "Timeout", {"ok": False, "reason": "timeout"}
        except Exception as e:
            return False, str(e), {"ok": False, "exception": str(e)}

    def start_service(self):
        cmds = self._get_cmds("start_cmd", "start_cmds")
        if cmds:
            return self._run_cmds(cmds)
        
        logging.info("Starting Mineru Service...")
        out, err = self.ssh.execute_command(f"docker inspect -f '{{{{.State.Running}}}}' {self.container_name}", sudo=self.sudo)
        
        container_running = False
        if out and "true" in out.lower():
            container_running = True
        elif "No such object" in err or "Error" in err:
            # Container doesn't exist, create it
            api_port = int(self.config.get("api_port") or self.config.get("port") or 8000)
            run_cmd = (
                f"docker run --gpus all --shm-size 32g "
                f"-p 30000:30000 -p 7860:7860 -p {api_port}:8000 "
                f"--ipc=host -itd --name {self.container_name} "
                f"-e MINERU_MODEL_SOURCE=local "
                f"mineru:latest /bin/bash"
            )
            out, err = self.ssh.execute_command(run_cmd, sudo=self.sudo)
            if err and "Conflict" not in err:
                return False, f"Docker run failed: {err}"
            container_running = True
            time.sleep(5) # Wait for container init

        if not container_running:
            # Start existing stopped container
            out, err = self.ssh.execute_command(f"docker start {self.container_name}", sudo=self.sudo)
            if err: return False, f"Docker start failed: {err}"
            time.sleep(3)

        internal_cmd = str(self.config.get("api_start_cmd") or "nohup mineru-api --host 0.0.0.0 --port 8000 > /vllm-workspace/api.log 2>&1 &")
        full_exec_cmd = f"docker exec -d {self.container_name} bash -c '{internal_cmd}'"
        
        out, err = self.ssh.execute_command(full_exec_cmd, sudo=self.sudo)
        if err:
            return False, f"Internal API start failed: {err}"
            
        return True, "Service started command sent"

    def stop_service(self):
        cmds = self._get_cmds("stop_cmd", "stop_cmds")
        if cmds:
            return self._run_cmds(cmds)
        out, err = self.ssh.execute_command(f"docker stop {self.container_name}", sudo=self.sudo)
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

    def _get_cmds(self, key_single: str, key_multi: str) -> List[str]:
        if self.config.get(key_multi) and isinstance(self.config.get(key_multi), list):
            return [str(x) for x in self.config.get(key_multi) if str(x).strip()]
        v = str(self.config.get(key_single) or "").strip()
        return [v] if v else []

    def _run_cmds(self, cmds: List[str]):
        if not cmds:
            return False, "Missing command"
        wrapper = str(self.config.get("ssh_command_wrapper") or "").strip() or None
        for cmd in cmds:
            c = str(cmd or "").strip()
            if c.startswith("@script:") or c.startswith("script:"):
                ########## 在这里使用“脚本式启停命令” ##########
                # 功能是：
                # - YAML 的 start_cmds/stop_cmds/restart_cmds 支持写 @script:相对路径
                # - 程序会把本地脚本上传到远端 /tmp/heartbeat_monitor_scripts/<service_id>/ 并用 bash 执行
                #
                # 样例是：
                # - "@script:ops_scripts/<service_id>/restart.sh"
                #
                # 参考文档是：
                # - docs/config_reference.md（3.1 使用脚本文件）
                # - ops_scripts/README.md（目录规范与示例）
                ########## 逻辑开始 ##########
                local_path = c.split(":", 1)[1].strip()
                if not os.path.isabs(local_path):
                    root_dir = Path(__file__).resolve().parents[1]
                    local_path = str((root_dir / local_path).resolve())
                if not os.path.exists(local_path):
                    return False, f"Script not found: {local_path}"
                remote_dir = f"/tmp/heartbeat_monitor_scripts/{self.service_id}"
                remote_path = f"{remote_dir}/{os.path.basename(local_path)}"
                out, err = self.ssh.execute_command(f"mkdir -p {remote_dir}", sudo=self.sudo, wrapper=wrapper)
                if err:
                    return False, err
                up_ok, up_msg = self.ssh.upload_file(local_path, remote_path)
                if not up_ok:
                    return False, up_msg
                out, err = self.ssh.execute_command(f"chmod +x {remote_path}", sudo=self.sudo, wrapper=wrapper)
                if err:
                    return False, err
                out, err = self.ssh.execute_command(f"bash {remote_path}", sudo=self.sudo, wrapper=wrapper)
                if err:
                    return False, err
                continue
            out, err = self.ssh.execute_command(cmd, sudo=self.sudo, wrapper=wrapper)
            if err:
                return False, err
        return True, "OK"

    def _match_expected(self, response: requests.Response, expected: Any) -> Tuple[bool, str]:
        return match_expected(response, expected)

    def _normalize_multipart_form(self, extra_form: Any):
        if not extra_form:
            return []
        if isinstance(extra_form, list):
            return [(str(k), str(v)) for k, v in extra_form]
        if not isinstance(extra_form, dict):
            return [("value", str(extra_form))]
        items = []
        for k, v in extra_form.items():
            key = str(k)
            if isinstance(v, list):
                for one in v:
                    items.append((key, str(one)))
                continue
            if isinstance(v, (dict, tuple)):
                items.append((key, json.dumps(v, ensure_ascii=False)))
                continue
            if v is None:
                continue
            items.append((key, str(v)))
        return items


def create_service(service_id: str, cfg: Dict[str, Any], config_path: str) -> MineruService:
    return MineruService(service_id, cfg, config_path=config_path)
