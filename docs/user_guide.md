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
访问：`http://<监控机IP>:5000/`

### 2.3 本机快速验证（不配任何远程服务也能跑）
本项目自带一个本机测试服务：
```bash
python local_test_service.py
```
默认会监听 `127.0.0.1:18080`，配套配置文件在：
- [local_test.yaml](file:///d:/CODE/PyCODE/Heartbeat_Monitor/config/services/local_test.yaml)

你可以通过切换测试服务状态来验证告警链路：
```bash
curl -X POST http://127.0.0.1:18080/toggle
```

## 3. 服务类型（分类）与推荐策略
系统用 `category + on_failure` 来表达“这类服务如何纳管”。

### 3.1 API 类（能命令运维）
典型：API 服务、docker 容器、systemd 服务、可执行程序。
- `category: api`
- 检测：`test_api + expected_response`
- 运维：配置 `start/stop/restart_cmd(s)` 其一或多个
- 失败策略：
  - 仅提示：`on_failure: alert`
  - 自动重启：`on_failure: restart`（需要配置 `restart_cmds`）

### 3.2 网页类（只能看页面状态）
典型：业务门户/管理后台，用户必须在页面里点按钮或人工处理。
- `category: web`
- 检测：用 `test_api` 指向首页/登录页；`expected_response` 填关键字（例如 “登录”）
- 不配置任何 `start/stop/restart_cmd(s)`（页面按钮会自动禁用）
- 推荐：`on_failure: alert`

### 3.3 只监测，不自动跑定时（手工触发）
典型：容易误报、或希望按需检查。
- `auto_check: false`
- 在运维界面点“检测”即可手工触发

## 4. YAML 配置（新增服务的唯一入口）
目录：`config/services/`

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

典型 API 配置（失败自动重启）：
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
- 按钮：
  - 若未配置对应命令，会自动禁用（常见于网页类服务）
  - “检测”永远可用，用于手工触发一次检测
- 点开服务详情：
  - 查看最近一次检测 detail（HTTP 状态码、耗时、响应摘要、自动重启结果等）

## 7. 故障排查
- 看页面“最近 10 条错误日志”
- 看 `data/logs/monitor.log`（运行日志）
- 确认 `test_api` 在监控机上可访问（内网防火墙/DNS/代理）
- 对网页类：`expected_response` 建议填一个稳定的关键字，避免动态内容误判

## 8. 禁用/删除服务
- 临时不用：在该服务 YAML 里设置 `enabled: false`（不加载到页面）
- 永久删除：直接删除对应的 `config/services/<name>.yaml`
