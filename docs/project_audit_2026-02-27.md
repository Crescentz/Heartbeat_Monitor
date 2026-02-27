# 项目审计与目标总结（2026-02-27）

## 1. 项目完整目的
Heartbeat Monitor 是一个用于内网环境的“服务健康监控 + 运维控制”平台。

核心目标：
- 将多台机器上的 API / Web / 其他服务统一纳管与可视化。
- 通过统一 Web 页面查看状态、日志、策略，并执行启停重启操作。
- 在保证权限隔离的前提下，支持“只监控”与“可维护”两种模式。
- 以 YAML 配置优先，降低新增服务门槛；复杂场景再通过插件扩展。

## 2. 主要功能目标
- 健康检查：
  - 支持 HTTP 检查（GET/POST/PUT/PATCH/DELETE）
  - 支持可选文件上传检查
  - 支持 expected_response 规则匹配
- 失败策略：
  - `alert`：仅告警/记录
  - `restart`：失败后自动重启（需具备运维能力）
- 调度能力：
  - 每个服务单独控制自动检测开关
  - 支持 `10s`、`5m`、`1h`、`daily@02:30`、`weekly@mon 03:00`
- 权限控制：
  - 登录与会话鉴权
  - 超管/普通用户角色隔离
  - 服务绑定与用户级运维权限
- 可追溯性：
  - 错误日志（errors.jsonl）
  - 事件日志（events.jsonl）

## 3. 架构与职责
- `main.py`：应用启动入口，负责调度注册与 Web 启动。
- `core/monitor_engine.py`：统一检查与控制编排。
- `core/service_loader.py`：加载 `config/services/*.yaml` 并构建服务对象。
- `services/generic_service.py`：通用 HTTP + SSH 服务实现。
- `services/localproc_service.py`：本地进程服务实现。
- `monitor/webapp.py`：Flask 路由与 API 层。
- `templates/index.html`：前端页面与交互逻辑。

## 4. 本轮修复结果
### 后端修复
- 修复非法查询参数导致500：
  - `/api/services`
  - `/api/errors`
  - `/api/events`
- 增加管理端频率严格校验：
  - `/api/admin/schedules` 对非法 `check_schedule` 返回 `400 invalid_check_schedule`
- 增加服务绑定参数校验：
  - `/api/admin/bindings` 对不存在服务返回 `400 service_not_found`
- 增加控制动作参数校验：
  - `/api/control/<service_id>/<action>` 非法 action 返回 `400 unsupported_action`
  - 服务不存在返回 `404 service_not_found`

### 前端优化
- 修复筛选后分页越界导致的空页体验：
  - `loadAll()` 中自动回退到有效页码

### 可维护性提升
- 恢复并增强中文扩展注释（尤其是插件入口注释），按“面向用户阅读”风格保留详细说明。
- 补充基础接口注释，明确服务扩展契约与返回结构示例。

## 5. 扩展示例（插件机制）
YAML：
```yaml
name: 自定义服务
plugin: custom
test_api: http://127.0.0.1:9000/health
```

插件文件：
- `services/custom_service.py`

插件工厂函数：
```python
def create_service(service_id, cfg, config_path):
    ...
```

## 6. 频率校验示例
合法：
- `10s`
- `5m`
- `1h`
- `daily@02:30`
- `weekly@mon 03:00`

非法（管理端更新时返回400）：
- `weekly@bad`
- `abc`
- `daily@99:99`

## 7. 后续建议
- 增加 pytest 回归测试：参数容错、权限边界、频率校验。
- 增加前端自动化测试：管理弹窗、频率切换、分页边界。
- 逐步统一页面文案编码，减少历史内容中的乱码文本。

## 8. 本轮前端显性化优化（2026-02-27）
- 状态颜色：Unknown 由青色改为橙黄色，降低与 Running 的视觉混淆。
- 列结构重构：拆分为“运行状态 / 操作状态 / 服务维护”三列，降低单列信息密度。
- 运行状态列精简：只显示异常、运行、未知、禁用四种状态，不再混入策略信息。
- 操作状态列直达：支持自动检测开关、频率修改、自动重启开关、一键禁用、切到只监控/恢复可维护。
- 服务维护列显性：启动/停止/重启/检测统一展示，使用 `√/-/x` 三态；其中 `-` 表示“可维护但该动作未配置命令/脚本”。
- 逻辑收敛：移除前端重复失败策略入口，减少冲突与误操作。
- 接口增强：`/api/services` 新增 `action_state_*` 与 `action_mark_*` 字段，前端直接消费后端三态，不再本地重复推断。
- 本机一致性：`LocalProcService` 补齐 `start_capable/stop_capable/restart_capable` 与本机语义的 `auto_restart_effective`。
- 弹窗逻辑：日志弹窗创建前先移除同ID旧节点，避免重复与冲突。
- 分页逻辑：筛选后自动校正页码，避免空数据页。
