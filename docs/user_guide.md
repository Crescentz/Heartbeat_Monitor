# 用户使用手册

## 1. 你要解决什么问题
这套系统用来做两件事：
- 按固定周期检测服务“是否可用”（心跳）
- 在一个页面里集中看状态、看失败原因，并对“可运维的服务”做一键启停/重启

## 2. 运行方式
### 2.1 启动前自检
```bash
python doctor.py
```

### 2.2 安装依赖与启动
```bash
python -m pip install -r requirements.txt
python main.py
```
访问：`http://<监控机IP>:60005/`（会跳转到登录页 `/login`）

首次启动会自动初始化默认超管账号：`admin / admin`（登录后请立刻改密码）。

### 2.3 账号、权限与“看不到服务”
- 未登录：访问页面会跳到 `/login`；访问 `/api/*` 会返回 401
- 超管（admin）：可看到所有服务，并可在右上角“管理”里创建用户、重置密码、配置“服务绑定”
- 普通用户：只能看到绑定给自己的服务（如果列表为空，优先检查是否已被超管绑定）。默认不具备“启停/重启”权限，只能查看与发起检测；需要超管在“管理-用户列表”里开启运维权限后才可操作
- 服务级“只监控/可运维”：即使是超管，也可以把某个服务切到“只监控”，此时任何人都不能启停/重启且失败不会自动重启，避免误操作；该按钮只会在服务配置了启停/重启能力时出现。系统首次生成开关文件时会把当时已加载的服务默认设为“可运维”，之后新增的服务若未显式设置则默认处于“只监控”，需超管在服务列表操作区手动切换为“可运维”
- 服务级“自动检测（定时心跳）”：新增服务被纳管后默认先不参与定时检测（避免误报/误操作）；需要超管在服务列表的“频率”列开关或弹窗里开启。系统首次生成自动检测开关文件时会把当时已加载的服务默认设为“开启自动检测”，之后新增的服务若未显式设置则默认关闭

### 2.4 本机快速验证（不配任何远程服务也能跑）
本项目自带一个本机测试服务：
```bash
python local_test_service.py
```
默认会监听 `127.0.0.1:18080`，配套配置文件在：
- [local_test.yaml](file:///d:/CODE/PyCODE/Heartbeat_Monitor/config/samples/local_test.yaml)（复制到 `config/services/` 后再启用）

提示：超管可直接在服务列表的“频率”列开关自动检测，或点击频率弹窗编辑；也可以在“管理-服务绑定/检测频率”里把某个服务的检测频率设置为 `off`，快速关闭自动检测（无需改 YAML）。
提示：超管可在“自动检测与频率”弹窗里设置“失败后自动重启”；该开关只影响后续失败的处理方式，且服务必须处于“可运维”才会执行重启。

你可以通过切换测试服务状态来验证告警链路：
```bash
curl -X POST http://127.0.0.1:18080/toggle
```

另外仓库还内置一个“失败重启”的完整本机样例（可在 Win/Linux 直接跑，不依赖本机 SSH）：
- 示例 API：[local_restart_api.py](file:///d:/CODE/PyCODE/Heartbeat_Monitor/local_restart_api.py)（监听 `127.0.0.1:18081`）
- 监控配置：[local_restart_demo.yaml](file:///d:/CODE/PyCODE/Heartbeat_Monitor/config/samples/local_restart_demo.yaml)（复制到 `config/services/` 后启用）

## 3. 服务类型（分类）与推荐策略
系统用 `category + on_failure` 来表达“这类服务如何纳管”。

### 3.1 API 类（仅监控或可运维）
典型：API 服务、docker 容器、systemd 服务、可执行程序。
- `category: api`
- 检测：`test_api + expected_response`
- 运维（可选）：配置 `start/stop/restart_cmd(s)` 其一或多个（需要能 SSH 登录目标机；若做不到就保持为空=仅监控）
- 失败策略：
  - 仅提示：`on_failure: alert`
  - 自动重启：`on_failure: restart`（需要配置 `restart_cmds`）

### 3.2 网页类（只能看页面状态）
典型：业务门户/管理后台，用户必须在页面里点按钮或人工处理。
- `category: web`
- 检测：用 `test_api` 指向首页/登录页；`expected_response` 填关键字（例如 “登录”）
- 不配置任何 `start/stop/restart_cmd(s)`（页面按钮会自动禁用）
- 推荐：`on_failure: alert`

### 3.3 本机服务（无需 SSH，本机启停/重启）
典型：服务运行在监控机本机（Windows/Linux 都可）。
- 用 `plugin: "localproc"`（本机子进程方式）
- 本机服务不局限于本项目目录下的 Python 脚本：也可以是 docker/java/systemctl 等本机命令
- 推荐用 `start/stop/restart_cmd(s)` 写本机命令（在监控机本机执行），必要时配 `local_cwd`
- 也可以填 `local_script/local_args` 启动本机 Python 子进程（路径可为绝对路径或相对项目根目录）
- `ssh_user/ssh_password/sudo_password` 都不需要填写
- 若你只想监控本机服务而不想由页面启停：同样可以不配置任何命令字段，只保留检测字段

### 3.4 只监测，不自动跑定时（手工触发）
典型：容易误报、或希望按需检查。
- `auto_check: false`
- 在运维界面点“检测”即可手工触发
 - 或在管理界面把该服务“检测频率”设置为 `off`（无需改 YAML）
提示：手工“检测”不会触发自动重启；自动重启只会在定时检测失败且服务处于“可运维”时执行。

### 3.5 检测频率（每秒/每分钟/每天固定时间/每周等）
推荐在 YAML 中配置 `check_schedule`，例如：
- `10s` / `5m` / `1h`
- `daily@02:30`（每天 02:30）
- `weekly@mon 03:00`（每周一 03:00）

也可以在页面右上角“管理”->“服务绑定/检测频率”里直接修改每个服务的检测频率（仅超管可见，修改后会自动保存并立即生效；也可点“保存变更”批量保存）。

## 4. YAML 配置（新增服务的唯一入口）
目录：`config/services/`
参考样例：`config/samples/`（不自动加载；复制到 `config/services/` 后再启用）

最小可用配置（仅监测 + 仅提示）：
```yaml
id: "portal_web_01"
name: "业务门户（网页）"
description: "无API，失败仅提示人工处理"
category: "web"
auto_check: true
on_failure: "alert"

host: "192.168.1.130"
test_api: "http://192.168.1.130/"
expected_response: "登录"
timeout_s: 10
```

典型 API 配置（仅监控，无 SSH）：
```yaml
enabled: true
id: "api_only_sample"
name: "HTTP API 监控（仅监控）"
category: "api"
auto_check: true
on_failure: "alert"

host: "192.168.1.120"
test_api: "http://192.168.1.120:9000/health"
expected_response:
  ok: true
timeout_s: 10
```

典型 API 配置（可运维：失败自动重启，需 SSH）：
```yaml
id: "demo_api_01"
name: "Demo API"
description: "示例：HTTP检测 + docker 重启"
category: "api"
auto_check: true
on_failure: "restart"
auto_fix: true

host: "192.168.1.120"
test_api: "http://192.168.1.120:9000/health"
expected_response: "ok"
timeout_s: 10

ssh_port: 22
ssh_user: "ubuntu"
ssh_password: "REPLACE_ME"
sudo_password: "REPLACE_ME"
restart_cmds:
  - "sudo docker restart demo_api_container"
```

字段完整参考： [config_reference.md](file:///d:/CODE/PyCODE/Heartbeat_Monitor/docs/config_reference.md)

## 4.1 每个服务的运维文档（前端展示）
你可以在每个服务的 YAML 中填 `ops_doc`，用于前端点击“运维文档”后展示固定模板的运维内容（监控说明/启停步骤/排障/联系人/API 文档等）。
参考模板： [services_template.yaml](file:///d:/CODE/PyCODE/Heartbeat_Monitor/config/services_template.yaml)

## 4.2 复杂启停命令建议用脚本
对于很长的 docker/systemd/多步命令，推荐把命令写进脚本文件，再在 YAML 里引用脚本路径，避免 YAML 里堆叠超长命令。

目录建议：
- `ops_scripts/<service_id>/start.sh`
- `ops_scripts/<service_id>/stop.sh`
- `ops_scripts/<service_id>/restart.sh`

YAML 写法示例：
```yaml
start_cmds:
  - "@script:ops_scripts/example_service/start.sh"
stop_cmds:
  - "@script:ops_scripts/example_service/stop.sh"
restart_cmds:
  - "@script:ops_scripts/example_service/restart.sh"
```
兼容写法：`script:ops_scripts/...`（不带 `@`），但推荐统一写 `@script:`。

执行逻辑：
- 监控程序会把脚本上传到远端：`/tmp/heartbeat_monitor_scripts/<service_id>/<脚本名>`
- 然后执行：`bash <远端脚本路径>`（会继承该服务的 `sudo` 与 `ssh_command_wrapper` 配置）

## 5. SSH 登录方式
当且仅当你配置了 `start/stop/restart_cmd(s)` 时，才需要 SSH 凭据。

支持两种方式：
- 密码：`ssh_password`
- 私钥：`ssh_private_key`（私钥文本）或 `ssh_private_key_path`（私钥文件路径）

### 5.1 长命令脚本（conda activate / cd / source 等）
建议使用：
- `*_cmds`（多条命令）拆分步骤
- 或使用 `ssh_command_wrapper: "bash -lc"` 让命令在 login shell 中执行

## 6. 运维界面怎么用
- 列表页：看“类别/策略/状态/失败原因/最后检测时间”
- 筛选：支持关键字（服务名/ID/host/检测地址/描述/类别）+ 类别 + 失败策略 + 状态 + 只看失败
- 按钮：
  - 若未配置对应命令，会自动禁用（常见于网页类服务）
  - “检测”永远可用，用于手工触发一次检测
- 点开服务详情：
  - 查看最近一次检测 detail（HTTP 状态码、耗时、响应摘要、自动重启结果等）
- 右上角“项目信息”：查看版本号、更新时间与更新记录
- 页面底部日志区：
  - “错误日志”：失败原因
  - “事件日志”：检测成功/失败、手工启停/重启/检测、自动重启等

### 6.1 服务禁用/启用（超管）
有些服务可能临时不用检测/管控，超管可在服务列表“操作”列直接点击“禁用/启用”：
- 禁用后：不再参与定时检测；前台按钮（启动/停止/重启/检测）会被禁用；状态显示为 Disabled
- 启用后：恢复定时检测与前台操作

## 7. 故障排查
- 看页面“最近 10 条错误日志”
- 看 `data/logs/monitor.log`（运行日志）
- 确认 `test_api` 在监控机上可访问（内网防火墙/DNS/代理）
- 对网页类：`expected_response` 建议填一个稳定的关键字，避免动态内容误判

## 8. 禁用/删除服务
- 临时不用：在该服务 YAML 里设置 `enabled: false`（不加载到页面）
- 永久删除：直接删除对应的 `config/services/<name>.yaml`
