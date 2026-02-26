# 维护者手册

## 1. 项目启动链路（从 main.py 开始）
- [main.py](file:///d:/CODE/PyCODE/Heartbeat_Monitor/main.py)
  - 依赖检查（未安装时提示安装 requirements）
  - 目录初始化（data/logs）
  - 加载服务：`config/services/*.yaml`
  - 启动定时检测（按服务独立建 job；未配置 `check_schedule` 时默认 30m）
  - 启动后全量检查：放在后台线程执行，避免 Web 端口启动被阻塞
  - 启动 Flask Web

## 2. 服务加载机制（新增服务不改 main.py）
- [service_loader.py](file:///d:/CODE/PyCODE/Heartbeat_Monitor/core/service_loader.py)
  - 支持单服务 dict、多服务 list、或 `services: [...]`
  - `enabled: false` 的服务会被跳过（用于临时下线/停用服务）
  - YAML 解析失败/插件加载失败不会导致系统退出，会生成一个“配置加载失败”的服务对象（便于在页面直接看到问题）
- 插件规则：
  - YAML：`plugin: "<plugin>"`
  - 文件：`services/<plugin>_service.py`
  - 必须暴露：`create_service(service_id, cfg, config_path)`

## 3. BaseService 约定（页面展示字段从这里来）
- [base_service.py](file:///d:/CODE/PyCODE/Heartbeat_Monitor/core/base_service.py)
  - `check_health() -> (ok, message, detail)`
  - `start_service()/stop_service()/restart_service() -> (ok, message)`
  - `get_info()` 负责汇总展示字段（状态、故障率、分类、策略、按钮可用性）

## 4. 定时检测与失败策略
- [monitor_engine.py](file:///d:/CODE/PyCODE/Heartbeat_Monitor/core/monitor_engine.py)
  - `auto_check: false` 的服务不参与定时检测（仍可手工点“检测”）
  - `on_failure: alert`：失败告警（仅记录错误与事件）
  - `on_failure: restart`：失败后尝试执行 `restart_service()`（要求配置了 restart 命令）
  - 自动处理结果会额外写入错误日志（目前不合并到 `last_test_detail`）

## 5. Web 运维界面
- 后端路由：[webapp.py](file:///d:/CODE/PyCODE/Heartbeat_Monitor/monitor/webapp.py)
- 模板：[index.html](file:///d:/CODE/PyCODE/Heartbeat_Monitor/templates/index.html)
- 项目信息弹窗：右上角“项目信息”按钮触发；数据源：[app_info.py](file:///d:/CODE/PyCODE/Heartbeat_Monitor/core/app_info.py)（作者/版本/更新时间/更新记录）
- 错误日志：[error_log.py](file:///d:/CODE/PyCODE/Heartbeat_Monitor/core/error_log.py)
- 事件日志：[event_log.py](file:///d:/CODE/PyCODE/Heartbeat_Monitor/core/event_log.py)
- 账号与权限：[user_store.py](file:///d:/CODE/PyCODE/Heartbeat_Monitor/core/user_store.py)、[acl_store.py](file:///d:/CODE/PyCODE/Heartbeat_Monitor/core/acl_store.py)
- 禁用开关存储：[disabled_service_store.py](file:///d:/CODE/PyCODE/Heartbeat_Monitor/core/disabled_service_store.py)
- 运维模式（只监控/可运维）存储：[ops_mode_store.py](file:///d:/CODE/PyCODE/Heartbeat_Monitor/core/ops_mode_store.py)（支持单服务与批量切换）

## 6. SSH 执行与鉴权
- [ssh_manager.py](file:///d:/CODE/PyCODE/Heartbeat_Monitor/core/ssh_manager.py)
  - 支持密码与私钥（OpenSSH）两种登录方式
  - 支持 sudo（向 stdin 写入 sudo_password）
  - 支持命令包装器（如 `ssh_command_wrapper: bash -lc`），适配 conda/source 等场景
  - 支持脚本上传（用于 `@script:` 方式的复杂启停命令）

## 6.1 复杂启停命令：@script 机制
- 入口：服务 YAML 的 `start_cmds/stop_cmds/restart_cmds`
- 写法：`@script:ops_scripts/<service_id>/<name>.sh`
- 行为：上传到远端 `/tmp/heartbeat_monitor_scripts/<service_id>/`，执行 `bash <remote_script>`
- 实现：GenericService / MineruService 的 `_run_cmds`

## 7. 自检脚本（改配置先跑）
- [doctor.py](file:///d:/CODE/PyCODE/Heartbeat_Monitor/doctor.py)
  - 不联网、不连 SSH
  - 只做依赖与 YAML 字段/插件文件的静态检查

## 8. 扩展建议
- 新增一种“检测形态”时：
  - 优先扩展通用服务（GenericService）的检测能力（例如增加 headers、cookie、认证等）
  - 再考虑通过插件实现特例，避免主逻辑膨胀
- 对于网页类服务：
  - 建议使用 `expected_response` 的“稳定关键字”减少误判
