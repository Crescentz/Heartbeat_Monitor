from __future__ import annotations

from typing import Any, Dict

APP_INFO: Dict[str, Any] = {
    "name": "Heartbeat Monitor",
    "author": "CC",
    "version": "1.3.6",
    "updated_at": "2026-02-27",
    "latest": {
        "title": "更新内容（当前版本）",
        "items": [
            "后端增强：/api/services 新增动作三态字段（action_state_*/action_mark_*）",
            "判定统一：动作可执行性按用户权限、禁用状态、运维模式和动作能力一致计算",
            "本机能力修复：LocalProcService 补齐 start/stop/restart_capable 与 auto_restart_effective",
            "前端维护列：改为消费后端三态，显式展示 √/-/x（- 表示可维护但未配该动作命令）",
            "前端操作列：区分“自动重启开/关”与“只监控/可维护”入口，避免文案混淆",
            "文档同步：README/用户手册/配置参考/更新日志统一术语与规则",
        ],
    },
    "history": [
        {
            "version": "1.3.6",
            "date": "2026-02-27",
            "items": [
                "后端：/api/services 输出 action_state_*/action_mark_* 三态字段",
                "后端：统一动作三态判定逻辑，避免前后端重复推断",
                "后端：LocalProcService 补齐能力字段与自动重启生效判定",
                "UI：服务维护按钮改为 √/-/x 三态显式化",
                "UI：操作状态新增自动重启开/关按钮",
            ],
        },
        {
            "version": "1.3.5",
            "date": "2026-02-27",
            "items": [
                "UI：拆分运行状态、操作状态、服务维护三列",
                "UI：运行状态列仅保留四种核心状态",
                "UI：操作状态列支持自动检测/频率/禁用/只监控一级操作",
                "UI：服务维护按钮增加 √/× 与灰色禁用区分",
                "优化：移除前端重复的策略操作入口，降低操作复杂度",
            ],
        },
        {
            "version": "1.3.4",
            "date": "2026-02-27",
            "items": [
                "UI：移除“策略列/频率列”，策略信息收敛到状态列",
                "UI：状态列新增一级操作（自动检测/频率/失败策略/运维模式/禁用）",
                "UI：操作列去除重复能力徽章，仅保留启动/停止/重启/检测",
                "后端：服务信息新增 auto_restart_effective 字段",
                "文档：同步更新 README、用户手册、配置参考、审计文档",
            ],
        },
        {
            "version": "1.3.3",
            "date": "2026-02-27",
            "items": [
                "UI：Unknown 状态色调整为橙黄色",
                "UI：状态列集中展示自动检测、运维模式、禁用状态",
                "UI：策略列“失败自动重启”改为显性文字徽章",
                "UI：移除行内管理下拉，改为直接切换按钮",
                "UI：操作能力增加 ✅/❌ 标识，提升可用性识别",
                "UI：日志弹窗去重，避免重复创建导致冲突",
                "治理：新增运行态文件忽略规则，减少无效变更",
            ],
        },
        {
            "version": "1.3.2",
            "date": "2026-02-27",
            "items": [
                "修复：/api/services、/api/errors、/api/events 对非法查询参数容错",
                "修复：/api/admin/schedules 对无效 check_schedule 返回400",
                "修复：/api/admin/bindings 校验 service_id 必须存在",
                "修复：/api/control 非法 action 返回400，服务不存在返回404",
                "优化：前端分页越界自动回退到有效页",
                "文档：新增项目审计与目标文档，补充中文扩展注释说明",
            ],
        },
        {
            "version": "1.3.1",
            "date": "2026-02-26",
            "items": [
                "UI：服务状态显示与策略列信息更清晰；支持运维模式一键切换",
                "UI：服务表格顶部同步横向滚动条",
                "文档：统一“失败告警/自动重启/只监控/可运维”术语与说明",
            ],
        },
    ],
}
