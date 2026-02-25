# 配置参考（YAML）

配置文件目录：`config/services/`

每个 YAML 可以是：
- 单个服务对象（dict）
- 多个服务对象列表（list）
- 或包含 `services: [...]` 的对象

模板： [services_template.yaml](file:///d:/CODE/PyCODE/Heartbeat_Monitor/config/services_template.yaml)

## 1. 通用字段
- `enabled`：是否启用该服务（false 表示禁用，不加载到页面）
- `id`：服务唯一ID（建议填写）；不填会用文件名生成
- `name`：展示名
- `description`：服务描述
- `host`：被监控服务器 IP/主机名
- `ssh_port`：SSH 端口
- `ssh_user`：SSH 用户名
- `ssh_password`：SSH 密码
- `ssh_private_key`：OpenSSH 私钥文本（可选；与 ssh_password 二选一）
- `ssh_private_key_path`：私钥文件路径（可选；与 ssh_password 二选一）
- `ssh_private_key_passphrase`：私钥口令（可选）
- `ssh_command_wrapper`：远程命令包装器（可选；例如 `bash -lc`，用于 conda/source 环境等）
- `sudo_password`：sudo 密码（可选；不填则复用 ssh_password）
- `sudo`：是否使用 sudo 执行命令（默认 true）
- `service_type`：标注用途（docker/systemd/custom），目前仅用于阅读，不影响逻辑
- `category`：服务类别（api/web/other），用于界面分类展示
- `auto_check`：是否参与定时检测（默认 true）
- `on_failure`：失败策略（alert=仅提示；restart=失败后自动重启）
- `auto_fix`：当 on_failure=restart 时是否执行自动处理（默认 true）

## 2. 检测字段（GenericService）
- `plugin`：留空则使用通用检测；填写插件名则加载 `services/<plugin>_service.py`
- `test_api`：检测 URL
- `test_method`：GET/POST（当 `test_payload` 非空时也会自动按 POST 处理）
- `test_payload`：POST JSON 请求体（可选）
- `expected_response`：
  - dict：要求响应 JSON 中指定 key/value 匹配
  - string：要求响应文本包含该子串
  - null/空：仅判断 HTTP 2xx
- `timeout_s`：请求超时秒数

### 文件上传检测（GenericService）
当需要文件上传检测时填：
- `test_file`：本机文件路径（相对路径从项目根目录算，例如 `data/test.pdf`）
- `file_field`：上传字段名（默认 `file`）
- `file_extra_form`：额外 form 字段（可选）

## 3. 启停命令字段
命令字段支持单条或多条两种写法：
- `restart_cmd` / `restart_cmds`
- `start_cmd` / `start_cmds`
- `stop_cmd` / `stop_cmds`

建议使用 `*_cmds`（多条），便于拆分：清理旧容器 -> docker run -> docker exec 启动进程。
