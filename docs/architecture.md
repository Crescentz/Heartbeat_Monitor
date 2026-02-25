# 系统架构（Architecture）

本项目的核心思想是：把“服务”抽象成统一接口，监控引擎只做编排与展示；新增服务尽量只加 YAML，不改主程序。

## 1. 组件与职责
- **main.py**：启动入口，负责依赖检查、加载服务、启动定时任务、启动 Web
- **core/service_loader.py**：扫描 `config/services/*.yaml` 并加载服务对象
- **services/generic_service.py**：通用服务实现（HTTP 检测 + SSH 命令启停），适用于大部分标准 API
- **services/<plugin>_service.py**：插件服务实现（复杂检测/非标准接口/多步调用/文件上传等）
- **core/monitor_engine.py**：对外提供 `check_all / control`，Web 与定时任务都只调用它
- **monitor/webapp.py + templates/index.html**：Web 运维界面
- **core/error_log.py**：错误日志落盘与最近 N 条查询

## 2. “服务”抽象
服务对象统一继承 [BaseService](file:///d:/CODE/PyCODE/Heartbeat_Monitor/core/base_service.py)，对外表现为：
- `check_health() -> (ok, message, detail)`：检测并返回结构化 detail（展示在详情弹窗）
- `start_service()/stop_service()/restart_service()`：通过 SSH 执行启动/停止/重启逻辑
- `get_info()`：返回 Web 展示所需字段（状态、故障率、运行时长等）

服务还支持通过配置表达“纳管方式”：
- `category`：服务分类（api/web/other）
- `auto_check`：是否参与定时检测
- `on_failure`：失败策略（alert=仅提示；restart=失败后自动重启）

## 3. 配置驱动（新增服务不改 main.py）
服务配置放在 `config/services/`：
- YAML 解析失败/插件加载失败不会导致系统崩溃，会以“配置加载失败”的虚拟服务显示在页面中（见 [InvalidService](file:///d:/CODE/PyCODE/Heartbeat_Monitor/services/invalid_service.py)）。
- 推荐新增服务只新增 YAML；只有在“检测方式必须写代码”时才新增插件文件。

## 4. 数据与日志
- `data/logs/monitor.log`：运行日志
- `data/logs/errors.jsonl`：错误日志（JSON Lines），页面默认展示最近 10 条
