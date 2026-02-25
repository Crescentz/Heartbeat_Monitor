# Heartbeat Monitor（内网服务心跳检测与启停管理）

本项目在一台“监控机”（通常是CPU服务器）上运行，通过：
- HTTP/文件上传做健康检测（可自定义）
- SSH 远程执行命令（支持 `sudo docker ...`）

来监测内网多台 CPU/GPU 服务器上的服务状态，并提供一个简单的 Web 运维界面用于查看状态与一键启停/重启。

## 1. 一句话使用流程（傻瓜式）
1. 复制模板为一个 YAML：`config/services/<服务名>.yaml`
2. 填 `category + test_api + expected_response`（可选再填 `restart_cmds` 做自动恢复）
3. 运行自检：`python doctor.py`
4. 安装依赖：`python -m pip install -r requirements.txt`
5. 启动：`python main.py`
6. 打开：`http://<监控机IP>:5000/`

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
3. 打开页面即可看到“本机测试服务”

## 3. 目录结构（你只需要关心这几个）
- `main.py`：启动入口（不需要因新增服务而改动）
- `config/services/`：服务配置目录（新增服务=新增 YAML）
- `services/`：服务插件目录（遇到“非标准接口”才需要写插件）
- `templates/index.html`：Web 运维页面模板
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
- `expected_response` 填写成功特征（支持 dict 精确匹配或 string 子串匹配）
- `category` 区分服务类型：`api/web/other`（影响界面展示与按钮可用性）
- `on_failure` 控制失败策略：`alert`（仅提示）或 `restart`（自动重启，需配置 `restart_cmds`）

Mineru 示例： [mineru.yaml](file:///d:/CODE/PyCODE/Heartbeat_Monitor/config/services/mineru.yaml)

## 6. Web 运维界面能看什么
页面：`/`
- 表格展示：类别、策略、状态、运行时长、故障率、最后检测时间、检测地址
- 按钮：启动/停止/重启/立即检测
- 点击服务行：查看服务描述、配置文件路径、最近一次 API 测试详情（响应摘要/耗时等）
- “最近 10 条错误日志”：按行展示（时间 + 服务 + 原因）

## 7. 新增服务的两种方式
### 7.1 只加 YAML（推荐）
1. 复制模板到 `config/services/<name>.yaml`
2. 填好 `category / test_api / expected_response`（可选 `restart_cmds`）
3. 重启监控程序即可自动加载

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
