from __future__ import annotations

import glob
import os
import sys
from typing import Any, Dict, List, Tuple


def _import_deps() -> List[str]:
    missing: List[str] = []
    for mod in ("flask", "apscheduler", "paramiko", "requests", "yaml"):
        try:
            __import__(mod)
        except Exception:
            missing.append(mod)
    return missing


def _load_yaml(path: str) -> Tuple[bool, Any, str]:
    try:
        import yaml
    except Exception as e:
        return False, None, f"missing_dependency: yaml ({e})"
    try:
        with open(path, "r", encoding="utf-8") as f:
            return True, yaml.safe_load(f), ""
    except Exception as e:
        return False, None, str(e)


def _as_service_items(data: Any) -> List[Dict[str, Any]]:
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict) and isinstance(data.get("services"), list):
        return [x for x in data["services"] if isinstance(x, dict)]
    if isinstance(data, dict):
        return [data]
    return []


def _validate_item(cfg: Dict[str, Any]) -> List[str]:
    if cfg.get("enabled") is False:
        return []
    errors: List[str] = []
    name = str(cfg.get("name") or "").strip()
    host = str(cfg.get("host") or cfg.get("ip") or "").strip()
    test_api = str(cfg.get("test_api") or "").strip()
    if not name:
        errors.append("missing: name")
    if not host:
        errors.append("missing: host")
    if not test_api:
        errors.append("missing: test_api")

    start_cmd = str(cfg.get("start_cmd") or "").strip()
    stop_cmd = str(cfg.get("stop_cmd") or "").strip()
    restart_cmd = str(cfg.get("restart_cmd") or "").strip()
    start_cmds = cfg.get("start_cmds") if isinstance(cfg.get("start_cmds"), list) else []
    stop_cmds = cfg.get("stop_cmds") if isinstance(cfg.get("stop_cmds"), list) else []
    restart_cmds = cfg.get("restart_cmds") if isinstance(cfg.get("restart_cmds"), list) else []
    needs_ssh = bool(start_cmd or stop_cmd or restart_cmd or start_cmds or stop_cmds or restart_cmds)

    if needs_ssh:
        ssh_user = str(cfg.get("ssh_user") or cfg.get("username") or "").strip()
        if not ssh_user:
            errors.append("missing: ssh_user")

        ssh_password = str(cfg.get("ssh_password") or cfg.get("password") or "").strip()
        ssh_private_key = str(cfg.get("ssh_private_key") or "").strip()
        ssh_private_key_path = str(cfg.get("ssh_private_key_path") or "").strip()
        if not ssh_password and not ssh_private_key and not ssh_private_key_path:
            errors.append("missing: ssh_password or ssh_private_key or ssh_private_key_path")
        if ssh_private_key and ssh_private_key_path:
            errors.append("conflict: ssh_private_key and ssh_private_key_path")
        if ssh_private_key and "BEGIN OPENSSH PRIVATE KEY" not in ssh_private_key and "BEGIN RSA PRIVATE KEY" not in ssh_private_key:
            errors.append("ssh_private_key_format_suspicious")

    plugin = str(cfg.get("plugin") or "").strip()
    if plugin:
        plugin_path = os.path.join("services", f"{plugin}_service.py")
        if not os.path.exists(plugin_path):
            errors.append(f"plugin_file_not_found: {plugin_path}")
    return errors


def main() -> int:
    print("Heartbeat Monitor Doctor")
    print("")

    missing = _import_deps()
    if missing:
        print("依赖缺失：", ", ".join(missing))
        print("请执行：python -m pip install -r requirements.txt")
        print("")

    os.makedirs(os.path.join("data", "logs"), exist_ok=True)

    config_dir = os.path.join("config", "services")
    paths = sorted(glob.glob(os.path.join(config_dir, "*.yml")) + glob.glob(os.path.join(config_dir, "*.yaml")))
    if not paths:
        print(f"未发现服务配置：{config_dir}/*.yaml")
        print("建议复制模板：config/services_template.yaml -> config/services/<name>.yaml")
        return 0

    total = 0
    bad = 0
    for path in paths:
        ok, data, err = _load_yaml(path)
        if not ok:
            bad += 1
            print(f"[BAD] {path}: {err}")
            continue
        items = _as_service_items(data)
        if not items:
            bad += 1
            print(f"[BAD] {path}: YAML内容为空或格式不支持")
            continue

        for cfg in items:
            total += 1
            service_id = str(cfg.get("id") or os.path.splitext(os.path.basename(path))[0]).strip()
            errors = _validate_item(cfg)
            if errors:
                bad += 1
                print(f"[BAD] {service_id} ({path}): " + "; ".join(errors))
            else:
                print(f"[OK ] {service_id} ({path})")

    print("")
    print(f"服务条目：{total}；存在问题：{bad}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
