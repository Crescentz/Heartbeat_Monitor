# 维护者手册

## 启动链路
- `main.py`
  - 初始化日志与运行目录。
  - 加载 `config/services/` 中的 YAML。
  - 根据运行时状态文件补齐服务开关。
  - 创建定时任务并启动 Flask Web。
- `monitor/webapp.py`
  - 创建 Web 应用与管理员接口。
  - 启动时会再次把服务对象与持久化状态文件对齐，确保页面和调度器看到的是同一套状态。

## 关键模块
- `core/service_loader.py`
  - YAML 加载入口，支持单服务、多服务列表和 `services: [...]`。
- `core/monitor_engine.py`
  - 对外统一提供 `check_one / check_all / control`。
  - 自动重启后的延迟复检也在这里完成。
- `core/runtime_state.py`
  - 统一运行时状态补齐逻辑。
  - 负责把 `auto_check / disabled / ops_enabled / failure_policy` 从 YAML 和持久化文件收敛到服务对象。
- `core/auto_check_store.py`
  - 存储服务级自动检测开关。
  - 当前约定：新纳管服务若未显式写 `auto_check`，默认先关闭定时检测。
- `core/ops_mode_store.py`
  - 存储“只监控/可维护”开关。
  - 首次生成时按服务自己的 `ops_default_enabled` 初始化，而不是全局一刀切。
- `core/acl_store.py`、`core/user_store.py`
  - 用户、密码、服务绑定与用户级运维权限。

## 前后端一致性约定
- 页面展示的 `auto_check / disabled / ops_enabled / on_failure` 必须以后端 `/api/services` 返回值为准。
- 新增状态开关时，先补 `core/runtime_state.py`，再更新 `monitor/webapp.py` 和前端模板。
- 不要在前端重复推断服务可操作性；服务维护按钮三态以 `/api/services` 的 `action_state_* / action_mark_*` 为准。

## 回归建议
- 静态检查：
  - `python doctor.py`
  - `python -m py_compile main.py core/*.py monitor/*.py services/*.py archive/dev_tools/*.py`
- 最小接口验证：
  - `python archive/dev_tools/__verify_home.py`
  - `python archive/dev_tools/__verify_disabled_api.py`
- 管理员常用操作回归：
  - `python archive/dev_tools/__e2e_admin_common_ops.py`

## 文档维护点
- `README.md`
  - 对外说明项目目标、部署方式、目录与常用操作。
- `docs/project_context.md`
  - 保存项目定位、部署目标和核心设计。
- `docs/changelog.md`
  - 记录行为变更，便于部署前审阅。
- `core/app_info.py`
  - 右上角“项目信息”弹窗的数据源。
