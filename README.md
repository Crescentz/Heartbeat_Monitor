# Heartbeat Monitor（内网服务心跳检测与启停管理）

本项目在一台“监控机”（通常是CPU服务器）上运行，通过：
- HTTP/文件上传做健康检测（可自定义）
- SSH 远程执行命令（支持 `sudo docker ...`）

来监测内网多台 CPU/GPU 服务器上的服务状态，并提供一个简单的 Web 运维界面用于查看状态与一键启停/重启。

## 1. 一句话使用流程（傻瓜式）
1. 复制模板或样例为一个 YAML：`config/services/<服务名>.yaml`
   - 模板：`config/services_template.yaml`
   - 样例：`config/samples/`（不自动加载；复制过来再启用）
2. 填 `category + test_api + expected_response`（可选再填 `restart_cmds` 做自动恢复）
   - 新增服务纳管后默认先不参与定时检测；登录后可在服务列表“操作状态”列直接开启“自动检测”并设置频率
3. 运行自检：`python doctor.py`
4. 安装依赖：`python -m pip install -r requirements.txt`
5. 启动：`python main.py`
   - 环境变量：`HBM_DEBUG=1` 可开启 debug；`HBM_HOST/HBM_PORT` 可修改监听地址与端口
6. 打开：`http://<监控机IP>:60005/`（会跳转到 `/login`）

首次启动会自动初始化默认超管账号：`admin / admin`（登录后请立刻改密码）。

## 2. 快速开始（推荐使用虚拟环境）
Windows（PowerShell）：
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python main.py
```

Linux：
```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python main.py
```

## 2.1 启动前自检（建议先跑一次）
```bash
python doctor.py
```
该命令会检查：
- 依赖是否安装
- `config/services/*.yaml` 是否能解析
- 关键字段是否缺失（例如 `test_api/插件文件/SSH配置(仅命令运维类)`）

## 2.2 本机快速验证（推荐同事先跑这个）
1. 启动本机测试服务：
```bash
python local_test_service.py
```
2. 启动监控程序（另开一个终端）：
```bash
python main.py
```
3. 浏览器打开 `http://127.0.0.1:60005/`，用 `admin/admin` 登录后即可看到内置示例服务（见 `config/services/demo_services.yaml`）

另外仓库还内置了一个“自动重启”的完整本机样例（无需本机 SSH）：[local_restart_demo.yaml](file:///d:/CODE/PyCODE/Heartbeat_Monitor/config/samples/local_restart_demo.yaml) + [local_restart_api.py](file:///d:/CODE/PyCODE/Heartbeat_Monitor/local_restart_api.py)（复制到 `config/services/` 后启用）。

## 3. 目录结构（你只需要关心这几个）
- `main.py`：启动入口（不需要因新增服务而改动）
- `config/services/`：服务配置目录（自动加载；新增服务=新增 YAML）
- `config/samples/`：参考样例目录（不自动加载；复制到 `config/services/` 后再启用）
- `services/`：服务插件目录（遇到“非标准接口”才需要写插件）
- `ops_scripts/`：复杂启停命令脚本目录（可选；配合 `@script:` 使用）
- `templates/index.html`：Web 运维页面模板
- `core/app_info.py`：项目信息与更新记录（前端“项目信息”卡片数据来源）
- `data/logs/errors.jsonl`：错误日志（最近N条从这里读）
 - `doctor.py`：启动前自检脚本（不联网、不连SSH）
 - `frontend_preview/`：纯前端离线预览（不跑后端也可查看界面）

## 4. 文档导航（建议按顺序看）
- 用户使用手册（配置/策略/常见场景）：[user_guide.md](file:///d:/CODE/PyCODE/Heartbeat_Monitor/docs/user_guide.md)
- 运维与配置字段参考：[config_reference.md](file:///d:/CODE/PyCODE/Heartbeat_Monitor/docs/config_reference.md)
- 架构与模块职责：[architecture.md](file:///d:/CODE/PyCODE/Heartbeat_Monitor/docs/architecture.md)
- 插件扩展规范：[extending.md](file:///d:/CODE/PyCODE/Heartbeat_Monitor/docs/extending.md)
- 维护者手册（代码扩展/测试建议）：[maintainer_guide.md](file:///d:/CODE/PyCODE/Heartbeat_Monitor/docs/maintainer_guide.md)

## 5. 服务如何配置（YAML）
模板文件：[services_template.yaml](file:///d:/CODE/PyCODE/Heartbeat_Monitor/config/services_template.yaml)

最常见的场景：只用 YAML + 通用检测，不写任何 Python 代码：
- `plugin` 留空（走通用服务 [generic_service.py](file:///d:/CODE/PyCODE/Heartbeat_Monitor/services/generic_service.py)）
- `test_api` 指向你的健康检查接口（GET 或 POST）
- `expected_response` 填写成功特征（支持 null/string/dict/list/规则断言；用于区分“HTTP 200 但业务失败”）
- `max_elapsed_ms` 可选：慢响应阈值（毫秒），便于区分“可达但很慢”
- `category` 区分服务类型：`api/web/other`（影响界面展示与按钮可用性）
- `check_schedule` 控制检测频率：`10s/5m/1h/daily@02:30/weekly@mon 03:00`（可选；不填默认 30m）
- `on_failure` 控制失败策略：`alert`（失败告警）或 `restart`（自动重启，需配置 `restart_cmds`）
- 对“重启后需要启动时间”的服务：可配置 `post_control_check_delay_s`（手工启停后复检延迟）与 `post_auto_restart_check_delay_s`（自动重启后复检延迟）
- 复杂启停命令建议写成脚本：在 `*_cmds` 里写 `@script:ops_scripts/<service_id>/start.sh`（脚本会自动上传到远端 `/tmp/heartbeat_monitor_scripts/<service_id>/` 并执行）

Mineru 示例： [mineru.yaml](file:///d:/CODE/PyCODE/Heartbeat_Monitor/config/samples/mineru.yaml)（复制到 `config/services/` 后再启用）
脚本式启停示例： [example_service.yaml](file:///d:/CODE/PyCODE/Heartbeat_Monitor/config/samples/example_service.yaml)

## 6. Web 运维界面能看什么
页面：`/`
- 表格展示：类别、运行状态、操作状态、服务维护、运行时长、故障率、最后检测时间、检测地址
- 筛选：关键字（输入自动应用）+ 类别 + 失败策略 + 状态 + 只看失败
- 服务维护按钮：启动/停止/重启/立即检测（`√`=可执行，`-`=可维护但该动作未配置命令，`x`=不可执行）
- 超管可直接在表格“操作状态”列一级操作：自动检测开关、频率修改、自动重启开关、一键禁用、切到“只监控/恢复可维护”
- 表格横向滚动：支持顶部同步滚动条与拖拽滚动，不需要拉到页面底部再横向滑动
- 点击服务行：查看服务描述、配置文件路径、最近一次 API 测试详情（响应摘要/耗时等）
- “错误日志”：失败原因（时间 + 服务 + 原因）
- “事件日志”：检测成功/失败、手工启停/重启/检测、自动重启等事件
- 超管可对服务做“禁用/启用”（禁用后不再定时检测且不允许前台操作）
- 右上角“项目信息”：查看版本号、更新时间与更新记录（维护入口：`core/app_info.py`）

账号与权限：
- 未登录访问会跳转到登录页 `/login`
- 超管可在右上角“管理”里创建用户、重置密码、并把服务绑定给指定用户；普通用户只会看到绑定给自己的服务
- “管理-服务绑定/检测频率”：修改后会自动保存，也可点“保存变更”批量保存；填 `off` 可关闭某服务的自动检测
- 防误操作：支持“用户级可运维权限”与“服务级只监控/可维护开关”（仅当该服务配置了启停/重启能力时才显示该按钮）
- 超管右上角支持“一键切换”把“支持维护”的服务批量切到“可维护”，或批量切到“只监控”

## 7. 新增服务的两种方式
### 7.1 只加 YAML（推荐）
1. 复制模板到 `config/services/<name>.yaml`
2. 填好 `category / test_api / expected_response`（可选 `restart_cmds`）
3. 重启监控程序即可自动加载

常见三类服务写法：
- 仅监控（无法 SSH 登录目标机）：不写任何 `start/stop/restart_cmd(s)`，只配置检测字段；按钮会自动禁用。样例：[web_only_sample.yaml](file:///d:/CODE/PyCODE/Heartbeat_Monitor/config/samples/web_only_sample.yaml)、[api_only_sample.yaml](file:///d:/CODE/PyCODE/Heartbeat_Monitor/config/samples/api_only_sample.yaml)
- 可运维（可 SSH）：补齐 ssh_* 并配置启停命令/脚本（支持 `@script:`）。样例：[example_service.yaml](file:///d:/CODE/PyCODE/Heartbeat_Monitor/config/samples/example_service.yaml)
- 本机服务（无需 SSH）：用 `plugin: "localproc"`，既可用 `start/stop/restart_cmd(s)` 写本机命令（docker/java/systemctl），也可用 `local_script` 启动本机 Python 子进程。样例：[local_docker_sample.yaml](file:///d:/CODE/PyCODE/Heartbeat_Monitor/config/samples/local_docker_sample.yaml)、[local_test_managed.yaml](file:///d:/CODE/PyCODE/Heartbeat_Monitor/config/samples/local_test_managed.yaml)、[local_restart_demo.yaml](file:///d:/CODE/PyCODE/Heartbeat_Monitor/config/samples/local_restart_demo.yaml)

### 7.2 写插件（适用于非标准服务）
当你需要“上传文件/签名鉴权/多步调用/特殊返回校验”时：
1. 新建文件：`services/<plugin>_service.py`
2. 需要提供工厂函数：`create_service(service_id, cfg, config_path)`
3. 在 YAML 里写：`plugin: "<plugin>"`

参考： [mineru_service.py](file:///d:/CODE/PyCODE/Heartbeat_Monitor/services/mineru_service.py)

## 8. 纯前端离线预览（不跑后端也能看页面）
打开 [frontend_preview/index.html](file:///d:/CODE/PyCODE/Heartbeat_Monitor/frontend_preview/index.html) 即可离线查看一个“示例数据版”的界面。

如果浏览器不允许直接打开本地文件（少数策略），可在该目录启动静态服务器：
```bash
cd frontend_preview
python -m http.server 5173
```
然后访问：`http://127.0.0.1:5173/`

## 9. 安全提示（内网也建议遵守）
- YAML 中包含 SSH/Sudo 密码属于敏感信息，建议：
  - 仅限内网运维主机可读
  - 后续可改为环境变量/独立凭据文件/堡垒机
- SSH 建议优先使用 `ssh_private_key_path` 引用私钥文件路径，不要把私钥内容写进 YAML；私钥文件权限建议设为仅管理员可读（Linux 可用 `chmod 600`）
- `data/` 下包含运行态数据（session secret、用户文件、日志、开关持久化文件等），不应提交到仓库（已在 `.gitignore` 中默认忽略）
- 首次启动默认 `admin/admin` 仅用于初始化，必须尽快修改密码

## 最新审计（2026-02-27）
- 完整项目目标、架构、修复项与扩展示例见：`docs/project_audit_2026-02-27.md`
