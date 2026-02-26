from __future__ import annotations

from typing import Any, Dict, List

APP_INFO: Dict[str, Any] = {
    "name": "Heartbeat Monitor",
    "author": "CC",
    "version": "1.2.0",
    "updated_at": "2026-02-26",
    "latest": {
        "title": "更新内容（当前版本）",
        "items": [
            "服务列表支持横向拖拽滚动与稳定的水平滚动条",
            "筛选增强：关键字/类别/失败策略/状态",
            "项目信息改为右上角按钮弹窗展示（版本/更新时间/更新记录）",
            "复杂启停命令支持 @script: 本地脚本自动上传远端执行",
            "启动阶段全量检查改为后台线程，Web 更快可访问",
            "存储文件写入改为原子写，减少异常断电/中断导致的损坏风险",
        ],
    },
    "history": [
        {
            "version": "1.2.0",
            "date": "2026-02-26",
            "items": [
                "UI：服务表格横向滚动修复、筛选增强、项目信息弹窗",
                "运维：@script 脚本式启停命令",
                "稳定性：引擎层异常兜底与存储原子写",
            ],
        },
        {
            "version": "1.1.0",
            "date": "2026-02-25",
            "items": [
                "增加服务级“只监控/可运维”防误操作开关",
                "补全配置参考与用户手册",
            ],
        },
        {
            "version": "1.0.0",
            "date": "2026-02-24",
            "items": [
                "初版：支持 HTTP 健康检查、SSH 启停与 Web 运维界面",
            ],
        },
    ],
}

