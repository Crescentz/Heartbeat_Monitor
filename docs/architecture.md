# 系统架构（Architecture）

本项目的核心思想是：把“服务”抽象成统一接口，监控引擎只做编排与展示；新增服务尽量只加 YAML，不改主程序。

## 1. 组件与职责
- **main.py**：启动入口，负责依赖检查、加载服务、启动定时任务、启动 Web
- **core/service_loader.py**：扫描 `config/services/*.yaml` 并加载服务对象
- **services/generic_service.py**：通用服务实现（HTTP 检测 + SSH 命令启停），适用于大部分标准 API
- **services/localproc_service.py**：本机子进程服务实现（HTTP 检测 + 本机启停/重启），用于跨平台本机样例或无需 SSH 的场景
- **services/<plugin>_service.py**：插件服务实现（复杂检测/非标准接口/多步调用/文件上传等）
- **core/monitor_engine.py**：对外提供 `check_one / check_all / control`，Web 与定时任务都只调用它
- **monitor/webapp.py + templates/index.html**：Web 运维界面
- **core/error_log.py**：错误日志落盘与最近 N 条查询
- **core/user_store.py + core/acl_store.py**：账号与权限（超管/普通用户、服务绑定）

## 2. “服务”抽象
服务对象统一继承 [BaseService](file:///d:/CODE/PyCODE/Heartbeat_Monitor/core/base_service.py)，对外表现为：
- `check_health() -> (ok, message, detail)`：检测并返回结构化 detail（展示在详情弹窗）
- `start_service()/stop_service()/restart_service()`：执行启动/停止/重启逻辑（可通过 SSH 或本机子进程）
- `get_info()`：返回 Web 展示所需字段（状态、故障率、运行时长等）

服务还支持通过配置表达“纳管方式”：
- `category`：服务分类（api/web/other）
- `auto_check`：是否参与定时检测
- `check_schedule`：检测频率（可选；支持 `10s/5m/1h/daily@02:30/weekly@mon 03:00`）
- `on_failure`：失败策略（alert=失败告警；restart=失败后自动重启）

## 3. Web 认证与授权
- Web 使用 session 登录，未登录访问 `/` 会跳转 `/login`，未登录访问 `/api/*` 返回 401（见 [webapp.py](file:///d:/CODE/PyCODE/Heartbeat_Monitor/monitor/webapp.py)）。
- 超管可管理用户与服务绑定；普通用户仅能看到/操作绑定给自己的服务（见 [acl_store.py](file:///d:/CODE/PyCODE/Heartbeat_Monitor/core/acl_store.py)、[user_store.py](file:///d:/CODE/PyCODE/Heartbeat_Monitor/core/user_store.py)）。

## 4. 配置驱动（新增服务不改 main.py）
服务配置放在 `config/services/`：
- YAML 解析失败/插件加载失败不会导致系统崩溃，会以“配置加载失败”的虚拟服务显示在页面中（见 [InvalidService](file:///d:/CODE/PyCODE/Heartbeat_Monitor/services/invalid_service.py)）。
- 推荐新增服务只新增 YAML；只有在“检测方式必须写代码”时才新增插件文件。

## 5. 数据与日志
- `data/logs/monitor.log`：运行日志
- `data/logs/errors.jsonl`：错误日志（JSON Lines），页面默认展示最近 10 条
- `data/logs/events.jsonl`：事件日志（检测成功/失败、手工启停、自动重启等）
- `data/logs/localproc_<service_id>.log`：本机子进程（localproc）stdout/stderr 日志（用于排查端口占用/启动失败等）
- `data/users.json`：用户数据（密码为 hash）
- `data/service_bindings.json`：服务与用户绑定关系
- `data/schedule_overrides.json`：前台设置的检测频率覆盖值
- `data/service_disabled.json`：服务禁用开关（超管前台设置）
- `data/service_auto_check.json`：服务级自动检测开关（纳管后默认关闭；开启后才创建定时任务）
- `data/service_failure_policy.json`：服务级失败策略覆盖（失败告警/自动重启）
- `data/localproc_pids/`：本机子进程（localproc）PID 记录（用于程序重启后仍可 stop/restart）

提示：`data/` 下均为运行态数据，默认不建议提交到仓库（见项目根目录 `.gitignore`）。
