# 配置参考（YAML）

配置文件目录：`config/services/`

样例目录：`config/samples/`（不自动加载；复制到 `config/services/` 后再启用）

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
- `ssh_port`：SSH 端口（仅“远端运维”需要）
- `ssh_user`：SSH 用户名（仅“远端运维”需要）
- `ssh_password`：SSH 密码（仅“远端运维”需要）
- `ssh_private_key`：OpenSSH 私钥文本（可选；与 ssh_password 二选一；仅“远端运维”需要）
- `ssh_private_key_path`：私钥文件路径（可选；与 ssh_password 二选一；仅“远端运维”需要）
- `ssh_private_key_passphrase`：私钥口令（可选；仅“远端运维”需要）
- `ssh_command_wrapper`：远程命令包装器（可选；例如 `bash -lc`；仅“远端运维”需要）
- `sudo_password`：sudo 密码（可选；仅在 sudo=true 且目标机需要口令时填写）
- `sudo`：是否使用 sudo 执行命令（仅命令执行时生效；默认 true/false 以模板为准）
- `service_type`：标注用途（docker/systemd/custom），目前仅用于阅读，不影响逻辑
- `category`：服务类别（api/web/other），用于界面分类展示
- `auto_check`：YAML 默认值（兼容旧配置）。实际是否参与定时检测以页面“自动检测”开关为准（持久化在 `data/service_auto_check.json`）；新纳管服务默认先不参与定时检测
- `check_schedule`：检测频率（可选；默认 30m）。支持：`10s`、`5m`、`1h`、`daily@02:30`、`weekly@mon 03:00`；管理界面也支持填 `off` 关闭自动检测（并会自动保存）
- `on_failure`：失败策略（alert=失败告警；restart=失败后自动重启）
- `auto_fix`：当 on_failure=restart 时是否执行自动处理（默认 true）
- `post_control_check_delay_s`：手工启动/重启后，延迟多少秒再做一次复检（用于“服务启动需要缓冲时间”的场景；上限 120s）
- `post_auto_restart_check_delay_s`：自动重启后，延迟多少秒再做一次复检（用于“服务重启后需要缓冲时间”的场景；上限 120s；默认 5s）
- `ops_doc`：服务运维文档（可选）。前端点击“运维文档”会按固定模板展示（见 services_template.yaml）
- 服务级“只监控/可运维”开关：该开关由前端超管操作持久化（不在 YAML 里写），存储在 `data/service_ops_mode.json`。切到“只监控”后任何人都不能启停/重启，且失败不会自动重启；该文件首次生成时会把当时已加载的服务默认设为“可运维”，之后新增的服务若未显式设置则默认按“只监控”处理，需超管手动切换为“可运维”

### 1.1 SSH 私钥怎么配置（推荐）
建议使用 `ssh_private_key_path` 引用私钥文件路径，不要把私钥内容写进 YAML（避免泄露）。

**关键点：这里写的是“私钥文件”（private key），不是公钥（.pub）**
- 私钥文件常见名字：`id_ed25519` / `id_rsa` / `heartbeat_monitor`（扩展名可有可无）
- 公钥文件常见名字：`id_ed25519.pub` / `id_rsa.pub`（这个不能填到 `ssh_private_key_path`）

**私钥文件里面长什么样（示例）**
- OpenSSH 新格式（常见）会以这一行开头：
  - `-----BEGIN OPENSSH PRIVATE KEY-----`
- 老的 PEM/RSA 格式会以这一行开头：
  - `-----BEGIN RSA PRIVATE KEY-----`
- 它们都属于“私钥内容”，必须保密，权限建议仅管理员可读。

**公钥文件（.pub）里面长什么样（示例）**
- 一般是一行文本（不要保密），形如：
  - `ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAI... heartbeat_monitor`
- 公钥需要追加到目标机的 `~/.ssh/authorized_keys` 里，才能用私钥免密登录。

步骤 1：在“监控机”准备私钥文件
- Linux：建议放在 `/root/.ssh/heartbeat_monitor` 或 `/home/<user>/.ssh/heartbeat_monitor`
- Windows：建议放在 `C:\\keys\\heartbeat_monitor`（或任意仅管理员可读目录）

步骤 2：把公钥加到被监控服务器的 authorized_keys
- 生成密钥（示例为 ed25519）：
  - `ssh-keygen -t ed25519 -f heartbeat_monitor -C heartbeat_monitor`
- 把 `heartbeat_monitor.pub` 追加到目标机 `~/.ssh/authorized_keys`

步骤 3：权限与路径写法
- Linux 权限建议：`chmod 600 /root/.ssh/heartbeat_monitor`
- YAML 中写法（推荐绝对路径）：
  - `ssh_private_key_path: "/root/.ssh/heartbeat_monitor"`
  - `ssh_private_key_passphrase: "xxx"`（若私钥有口令）
- 若写相对路径：会按项目根目录解析（例如 `keys/heartbeat_monitor`）

**补充：哪些命令需要 sudo**
- 默认 `sudo: true`：会在远端命令前加 `sudo -S`（并在需要时写入口令），适用于“运维账号不是 root，但需要提权”的场景。
- 如果你的远端账号本身就是 root，或 docker/systemctl 不需要 sudo：把 `sudo: false` 写到该服务里即可（此时不会加 sudo，也不会申请 pty）。

### 0.1 建议的“最简单心智模型”
建议只记 4 个开关/入口（其余字段按需用）：
- `enabled`（YAML）：是否加载到页面（=是否存在这个服务）
- “禁用/启用”（页面按钮）：临时禁用服务（禁用后不检测、不可操作）
- “只监控/可运维”（页面按钮）：是否允许启停/重启（防误操作总开关；仅当服务配置了启停/重启能力时才会出现）
- “自动检测”（服务列表/弹窗/管理面板）：开启后才会加入定时任务；填 `off` 表示关闭自动检测（不改 YAML 也能生效）
  - 超管也可在服务列表的“频率”列直接开关/编辑

### 0.2 开关/策略是否重复？（不重复，但容易混淆）
常见容易混淆的是“只监控/可运维”和“失败告警/自动重启”：
- “只监控/可运维”是运维总闸（`data/service_ops_mode.json`）：关闭后任何人都不能启停/重启，且定时检测失败也不会执行自动重启。
- “失败告警/自动重启”是失败策略（`on_failure` / `data/service_failure_policy.json`）：只决定“定时检测失败后怎么处理”；是否能执行重启仍取决于服务是否处于“可运维”且配置了重启能力（restart_cmds）。
- “禁用/启用”最高优先级（`data/service_disabled.json`）：禁用后既不参与检测，也不可操作。
- “自动检测”仅控制是否加入定时任务（`data/service_auto_check.json`）：关闭后仍可手工点“检测”，但手工检测不会触发自动重启。

## 2. 检测字段（GenericService）
- `plugin`：留空则使用通用检测；填写插件名则加载 `services/<plugin>_service.py`
- `test_api`：检测 URL
- `test_method`：GET/POST（当 `test_payload` 非空时也会自动按 POST 处理）
- `test_payload`：POST JSON 请求体（可选）
- `max_elapsed_ms`：慢响应阈值（毫秒，可选；超过则判定失败，便于区分“能访问但很慢”）
- `expected_response`：
  - null/空：仅判断 HTTP 2xx
  - string：要求响应文本包含该子串
  - dict：要求响应 JSON 中指定 key/value 匹配
  - list：多个候选条件（任意一个满足即通过）
  - dict + `__rules`：规则断言（适合“HTTP 200 但业务失败”的场景）
    - path 支持：`a.b.c`、`a.b[0].c`、以及 `$text`（响应原文）
    - op 支持：`exists/==/!=/contains/in/regex/gt/ge/lt/le/len_gt/len_ge/len_lt/len_le`
- `timeout_s`：请求超时秒数

### expected_response 示例
以下是一些常见写法（按需复制）：

**1）只看 HTTP 2xx（最简）**
```yaml
expected_response: null
```

**2）响应文本包含关键字（网页/文本类）**
```yaml
expected_response: "登录"
```

**3）JSON 字段精确匹配（常用 /health）**
```yaml
expected_response:
  ok: true
```

**4）多种候选返回（兼容不同版本）**
```yaml
expected_response:
  - { ok: true }
  - { status: "UP" }
```

**5）规则断言（区分“HTTP 200 但业务失败”）**
```yaml
expected_response:
  __type: "json"
  __rules:
    - { path: "code", op: "==", value: 0 }
    - { path: "data.text", op: "len_gt", value: 10 }
```

### Mineru / 类似“文件上传解析类”服务（插件示例）
这类服务通常没有统一的“/health”标准接口，监控程序会用一个固定样例文件（例如 `data/test.pdf`）调用业务接口来判断服务是否可用。
Mineru 示例接口：`POST /file_parse`，multipart 上传 `files` 字段（数组），并可附带参数（lang_list/backend/parse_method 等），详见示例配置 [mineru.yaml](file:///d:/CODE/PyCODE/Heartbeat_Monitor/config/samples/mineru.yaml)（复制到 `config/services/` 后再启用）。

### 本机子进程样例（localproc 插件）
用于跨平台本机演示“启动/停止/重启/自动重启”而无需 SSH。本机服务不一定是本项目内的 Python 脚本，也可以是 docker/java/systemctl 等本机命令：
- `plugin: "localproc"`
- 可选 `local_cwd`：本机命令/脚本的工作目录（可写绝对路径或相对项目根目录）
- **方式 A（推荐，适配最广）**：写本机命令 `start/stop/restart_cmd(s)`（在监控机本机执行）
- **方式 B（启动 Python 子进程）**：`local_script` + `local_args`（路径可为绝对路径或相对项目根目录）
- `local_args`：脚本参数数组（可选）
- 不需要填写 `ssh_user/ssh_password/sudo_password`
- 若某些“清理命令”允许失败（例如 docker rm -f 不存在的容器），可用 `@ignore:` 前缀忽略该条命令的非 0 返回码
- 可选 `start_restart_on_running: true`：当本机子进程已存在时，“启动”按钮改为执行一次 restart（用于演示环境中快速把服务从不健康状态拉回健康；生产环境不建议开启）

示例配置见：
- [local_test_managed.yaml](file:///d:/CODE/PyCODE/Heartbeat_Monitor/config/samples/local_test_managed.yaml)
- [local_alert_demo.yaml](file:///d:/CODE/PyCODE/Heartbeat_Monitor/config/samples/local_alert_demo.yaml)
- [local_restart_demo.yaml](file:///d:/CODE/PyCODE/Heartbeat_Monitor/config/samples/local_restart_demo.yaml)
- [local_docker_sample.yaml](file:///d:/CODE/PyCODE/Heartbeat_Monitor/config/samples/local_docker_sample.yaml)

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

### 3.0 仅监控（无 SSH）怎么写？
有些服务只能访问页面 URL 或 HTTP API（curl/python 能通），但无法 SSH 登录目标机做启停运维。此时建议：
- 不配置任何 `start/stop/restart_cmd(s)`（前端会自动禁用“启动/停止/重启”按钮）
- 只配置检测字段：`test_api / expected_response / timeout_s / check_schedule`
- `on_failure` 推荐用 `alert`（仅提醒人工处理）

参考样例：
- 网页类仅监控：[web_only_sample.yaml](file:///d:/CODE/PyCODE/Heartbeat_Monitor/config/samples/web_only_sample.yaml)
- API 类仅监控：[api_only_sample.yaml](file:///d:/CODE/PyCODE/Heartbeat_Monitor/config/samples/api_only_sample.yaml)

### 3.1 使用脚本文件（复杂命令推荐）
当命令非常复杂时，推荐把命令写进脚本文件，项目侧只引用脚本路径。

**1）脚本放哪里**
- 建议目录：`ops_scripts/<service_id>/`
- 建议文件：`start.sh` / `stop.sh` / `restart.sh`
- 示例目录见：[ops_scripts/README.md](file:///d:/CODE/PyCODE/Heartbeat_Monitor/ops_scripts/README.md)

**2）YAML 怎么写**
在 `*_cmds` 里写 `@script:` 形式的“本地脚本路径”（相对路径从项目根目录算；兼容 `script:`，但推荐统一写 `@script:`）：

```yaml
start_cmds:
  - "@script:ops_scripts/example_service/start.sh"
stop_cmds:
  - "@script:ops_scripts/example_service/stop.sh"
restart_cmds:
  - "@script:ops_scripts/example_service/restart.sh"
```
完整样例配置见：[example_service.yaml](file:///d:/CODE/PyCODE/Heartbeat_Monitor/config/samples/example_service.yaml)（复制到 `config/services/` 后按需修改）。

**3）执行原理（远端怎么跑）**
- 监控程序会把本地脚本上传到被监控机：`/tmp/heartbeat_monitor_scripts/<service_id>/<脚本名>`
- 然后执行：`bash <远端脚本路径>`
- 若该服务配置了 `sudo: true`，则脚本会以 sudo 方式执行
- 若配置了 `ssh_command_wrapper`，会在执行脚本时生效（用于加载远端环境）

**4）脚本注意事项**
- 用 bash 语法；出错请 `exit 1`，成功 `exit 0`（可配合 `set -euo pipefail`）
- 不要在脚本里写明文密码/密钥
- 远端临时目录在 `/tmp`，重启机器后可能丢失，属于预期行为

当只想直接写命令而不是脚本，仍可继续使用 `*_cmds` 写命令行字符串（与脚本方式可混用）。
