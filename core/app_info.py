from __future__ import annotations

from typing import Any, Dict

APP_INFO: Dict[str, Any] = {
    "name": "Heartbeat Monitor",
    "author": "CC",
    "version": "1.3.7",
    "updated_at": "2026-03-12",
    "latest": {
        "title": "当前版本更新",
        "items": [
            "统一运行时状态补齐逻辑，页面展示与调度器执行口径一致。",
            "新增服务补齐 auto_check 时，缺失字段默认关闭，更符合内网纳管的安全预期。",
            "ops_enabled 改为按服务自己的 ops_default_enabled 初始化，避免新增服务一刀切进入可维护状态。",
            "主页增加服务维护图例与自动刷新说明，并在弹窗打开或标签页隐藏时暂停自动刷新。",
            "新增管理员常用操作回归脚本，覆盖启停、自动检测、自动重启、禁用和用户绑定。",
            "README、维护手册、项目上下文和工具目录说明已同步更新。",
        ],
    },
    "history": [
        {
            "version": "1.3.7",
            "date": "2026-03-12",
            "items": [
                "运行时状态统一收敛到 core/runtime_state.py。",
                "新增服务自动检测默认值与文档说明保持一致。",
                "新增管理员常用操作回归脚本。",
                "前端自动刷新与页面提示优化。",
            ],
        },
        {
            "version": "1.3.6",
            "date": "2026-02-27",
            "items": [
                "后端输出 action_state_*/action_mark_* 三态字段。",
                "服务维护列改为消费后端三态，前端不再重复推断。",
                "本机 localproc 服务补齐能力字段与自动重启生效状态。",
            ],
        },
        {
            "version": "1.3.5",
            "date": "2026-02-27",
            "items": [
                "服务表格拆分为运行状态、操作状态、服务维护三列。",
                "失败策略、自动检测和运维模式入口统一收敛到操作状态列。",
            ],
        },
        {
            "version": "1.3.4",
            "date": "2026-02-27",
            "items": [
                "状态列整合策略与频率信息。",
                "后端新增 auto_restart_effective 字段。",
            ],
        },
    ],
}
