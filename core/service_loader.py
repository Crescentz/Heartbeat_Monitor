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
                    ########## 在这里扩展“新服务类型”（插件机制入口）##########
                    # 功能是：
                    # - 当 YAML 配置了 plugin: "<plugin>" 时，系统会加载 services/<plugin>_service.py
                    # - 并调用该模块的 create_service(service_id, cfg, config_path) 来创建服务对象
                    #
                    # 样例是：
                    # - YAML: config/samples/mineru.yaml（plugin: "mineru"；复制到 config/services/ 后再启用）
                    # - 插件: services/mineru_service.py（提供 create_service）
                    #
                    # 参考文档是：
                    # - docs/extending.md（插件规范）
                    #
                    # 参考内容是：
                    # - 插件文件命名：services/<plugin>_service.py
                    # - 必须暴露工厂函数：create_service(service_id, cfg, config_path)
                    ########## 扩展入口结束 ##########
                    service = _load_plugin_service(plugin, service_id, cfg, path)
                else:
                    ########## 在这里扩展“通用检测能力”（非插件）##########
                    # 功能是：
                    # - 当 plugin 为空时，默认走 GenericService（HTTP/文件上传检测 + SSH 启停）
                    #
                    # 样例是：
                    # - YAML: config/samples/local_test.yaml（复制到 config/services/ 后再启用）
                    #
                    # 参考文档是：
                    # - docs/config_reference.md（字段说明）
                    ########## 扩展入口结束 ##########
                    service = GenericService(service_id, cfg, config_path=path)
                services.append(service)
            except Exception as e:
                services.append(InvalidService(service_id, f"服务加载失败: {e}", config_path=path))
    return services


def _load_plugin_service(plugin: str, service_id: str, cfg: Dict[str, Any], config_path: str) -> BaseService:
    ########## 插件加载实现（一般不需要改）##########
    # 功能是：
    # - import services.<plugin>_service
    # - 校验 create_service 是否存在
    # - 调用 create_service(service_id, cfg, config_path)
    #
    # 如果你在新增插件时遇到 “must expose create_service(...)” 报错：
    # - 检查插件文件是否命名为 services/<plugin>_service.py
    # - 检查是否提供 create_service(service_id, cfg, config_path)
    ########## 实现结束 ##########
    module = importlib.import_module(f"services.{plugin}_service")
    if not hasattr(module, "create_service"):
        raise RuntimeError(f"services.{plugin}_service must expose create_service(service_id, cfg, config_path)")
    return module.create_service(service_id, cfg, config_path)
