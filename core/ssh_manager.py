import paramiko
import logging
import io
import os
from pathlib import Path
from typing import Optional, Tuple

class SSHManager:
    def __init__(
        self,
        ip: str,
        port: int,
        username: str,
        password: str,
        sudo_password: Optional[str] = None,
        private_key: Optional[str] = None,
        private_key_path: Optional[str] = None,
        private_key_passphrase: Optional[str] = None,
    ):
        self.ip = ip
        self.port = port
        self.username = username
        self.password = password
        self.sudo_password = sudo_password or password
        self.private_key = private_key
        self.private_key_path = private_key_path
        self.private_key_passphrase = private_key_passphrase
        self.client = None

    def connect(self):
        try:
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            pkey = self._load_pkey()
            if pkey is not None:
                self.client.connect(
                    self.ip,
                    port=self.port,
                    username=self.username,
                    pkey=pkey,
                    timeout=10,
                    look_for_keys=False,
                    allow_agent=False,
                )
            else:
                self.client.connect(
                    self.ip,
                    port=self.port,
                    username=self.username,
                    password=self.password,
                    timeout=10,
                    look_for_keys=False,
                    allow_agent=False,
                )
            return True
        except Exception as e:
            logging.error(f"SSH Connection failed to {self.ip}: {e}")
            return False

    def execute_command(self, command: str, sudo: bool = False, wrapper: Optional[str] = None) -> Tuple[Optional[str], str]:
        if not self.client:
            if not self.connect():
                return None, "Connection failed"

        try:
            if wrapper and str(wrapper).strip():
                command = _wrap_command(str(command), str(wrapper))

            if sudo:
                command = f"sudo -S -p '' {command}"
            
            stdin, stdout, stderr = self.client.exec_command(command, get_pty=bool(sudo))
            
            if sudo:
                stdin.write(self.sudo_password + "\n")
                stdin.flush()

            output = stdout.read().decode().strip()
            error = stderr.read().decode().strip()
            
            return output, error
        except Exception as e:
            logging.error(f"Command execution failed: {e}")
            # Try reconnecting once
            self.client.close()
            self.client = None
            return None, str(e)

    def upload_file(self, local_path: str, remote_path: str) -> Tuple[bool, str]:
        if not self.client:
            if not self.connect():
                return False, "Connection failed"
        try:
            sftp = self.client.open_sftp()
            try:
                sftp.put(local_path, remote_path)
            finally:
                try:
                    sftp.close()
                except Exception:
                    pass
            return True, "ok"
        except Exception as e:
            return False, str(e)

    def close(self):
        if self.client:
            self.client.close()

    def _load_pkey(self) -> Optional[paramiko.PKey]:
        key_data = None
        if self.private_key and str(self.private_key).strip():
            key_data = str(self.private_key).strip()
        elif self.private_key_path and str(self.private_key_path).strip():
            path = str(self.private_key_path).strip()
            if not os.path.isabs(path):
                root_dir = Path(__file__).resolve().parents[1]
                path = str((root_dir / path).resolve())
            if not os.path.exists(path):
                raise FileNotFoundError(f"Private key not found: {path}")
            with open(path, "r", encoding="utf-8") as f:
                key_data = f.read().strip()

        if not key_data:
            return None

        pw = self.private_key_passphrase
        bio = io.StringIO(key_data)
        loaders = [
            paramiko.Ed25519Key.from_private_key,
            paramiko.ECDSAKey.from_private_key,
            paramiko.RSAKey.from_private_key,
            paramiko.DSSKey.from_private_key,
        ]
        last_err: Optional[Exception] = None
        for loader in loaders:
            try:
                bio.seek(0)
                return loader(bio, password=pw)
            except Exception as e:
                last_err = e
                continue
        if last_err:
            raise last_err
        return None


def _wrap_command(command: str, wrapper: str) -> str:
    w = wrapper.strip()
    if not w:
        return command
    if "{}" in w:
        return w.format(command)
    return f"{w} {_sh_single_quote(command)}"


def _sh_single_quote(s: str) -> str:
    return "'" + s.replace("'", "'\"'\"'") + "'"
