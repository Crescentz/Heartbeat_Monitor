from __future__ import annotations

import glob
import importlib
import os
from typing import Any, Dict, List

import yaml

from core.base_service import BaseService
from services.generic_service import GenericService
from services.invalid_service import InvalidService


def _normalize_service_id(config_path: str, cfg: Dict[str, Any], index: int) -> str:
    explicit = str(cfg.get("id") or "").strip()
    if explicit:
        return explicit
    base = os.path.splitext(os.path.basename(config_path))[0]
    if index == 0:
        return base
    return f"{base}_{index+1}"


def load_services_from_dir(config_dir: str = os.path.join("config", "services")) -> List[BaseService]:
    services: List[BaseService] = []
    paths = sorted(glob.glob(os.path.join(config_dir, "*.yml")) + glob.glob(os.path.join(config_dir, "*.yaml")))
    for path in paths:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except Exception as e:
            service_id = os.path.splitext(os.path.basename(path))[0]
            services.append(InvalidService(service_id, f"YAML解析失败: {e}", config_path=path))
            continue
        items: List[Dict[str, Any]]
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict) and "services" in data and isinstance(data["services"], list):
            items = data["services"]
        elif isinstance(data, dict):
            items = [data]
        else:
            service_id = os.path.splitext(os.path.basename(path))[0]
            services.append(InvalidService(service_id, "YAML内容格式不支持", config_path=path))
            continue

        for i, cfg in enumerate(items):
            if not isinstance(cfg, dict):
                continue
            if cfg.get("enabled") is False:
                continue
            service_id = _normalize_service_id(path, cfg, i)
            plugin = str(cfg.get("plugin") or "").strip()
            try:
                if plugin:
                    service = _load_plugin_service(plugin, service_id, cfg, path)
                else:
                    service = GenericService(service_id, cfg, config_path=path)
                services.append(service)
            except Exception as e:
                services.append(InvalidService(service_id, f"服务加载失败: {e}", config_path=path))
    return services


def _load_plugin_service(plugin: str, service_id: str, cfg: Dict[str, Any], config_path: str) -> BaseService:
    module = importlib.import_module(f"services.{plugin}_service")
    if not hasattr(module, "create_service"):
        raise RuntimeError(f"services.{plugin}_service must expose create_service(service_id, cfg, config_path)")
    return module.create_service(service_id, cfg, config_path)

