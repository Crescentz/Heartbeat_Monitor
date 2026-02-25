# 项目上下文文档：多服务器服务心跳检测与管理系统

## 1. 项目概述
本项目旨在构建一个基于Python和Flask的内网服务监控管理系统。该系统运行在一台中央CPU服务器上，通过SSH远程连接和自定义API检测逻辑，监控内网中多台服务器（CPU/GPU）上的异构服务状态。

核心目标是提供一个统一的运维面板，用于查看服务健康状况、响应时间、故障日志，并提供一键启停和自动故障恢复功能。

## 2. 核心需求
### 2.1 架构需求
- **中心化管理**：单点部署监控程序，远程管理多台节点。
- **通信协议**：
  - **检测**：HTTP/HTTPS 请求（支持自定义Header, Body, 文件上传）。
  - **控制**：SSH (Paramiko) 执行 `sudo docker` 或系统命令。
- **可扩展性**：采用插件化或配置化设计。新增服务只需增加少量代码（继承基类）或配置文件，无需修改核心逻辑。

### 2.2 功能需求
- **心跳检测**：
  - 定时任务（如每30分钟）。
  - 支持复杂检测逻辑（如上传PDF测试OCR功能），不仅仅是端口通断。
- **分类纳管**：
  - 支持 API 类、网页类等分类。
  - 网页类以“可访问性/关键字”作为检测依据，不强制要求远程启停能力。
- **状态管理**：
  - 实时状态：运行中 / 异常 / 停止。
  - 统计指标：运行时长、故障率、最后一次失败日志。
- **自动恢复**：
  - 检测到异常时，自动记录日志。
  - 尝试自动重启服务（可选配置）。
- **Web运维界面**：
  - 展示服务列表、IP、端口、描述。
  - 操作按钮：启动、停止、重启、立即检测。
  - 日志查看。

### 2.3 目标环境
- **操作系统**：Linux (Ubuntu/CentOS)。
- **容器化**：目标服务多运行在Docker中。
- **网络**：内网环境，服务器之间互通。

## 3. Mineru 服务详情 (首个接入案例)
Mineru 是一个基于Docker的PDF OCR转换服务，部署在GPU服务器上。

- **服务器信息**：需在配置中指定IP, SSH端口, Sudo用户/密码。
- **Docker 启动命令**：
  ```bash
  sudo docker run --gpus all --shm-size 32g -p 30000:30000 -p 7860:7860 -p 8000:8000 --ipc=host -itd --name mineru_container mineru:latest /bin/bash
  ```
- **应用启动命令** (在容器内部执行)：
  ```bash
  nohup mineru-api --host 0.0.0.0 --port 8000 > /vllm-workspace/api.log 2>&1 &
  ```
  *(注：需设置环境变量 `MINERU_MODEL_SOURCE=local`)*
- **检测逻辑**：
  - 调用API上传预定义的PDF文件。
  - 验证返回结果是否包含OCR识别成功的标志。

## 4. 项目结构设计
```text
Heartbeat_Monitor/
├── config/
│   ├── services_template.yaml  # 服务配置模板
│   └── services/               # 服务实例配置目录（每个服务一个yaml）
├── core/
│   ├── base_service.py         # 服务基类（统一状态字段与接口）
│   ├── ssh_manager.py          # SSH连接管理
│   ├── service_loader.py       # 从 config/services/ 自动加载服务
│   ├── monitor_engine.py       # 检测与控制编排
│   ├── error_log.py            # 错误日志（最近N条）
│   └── storage.py              # 数据目录初始化
├── monitor/
│   └── webapp.py               # Flask Web运维界面
├── services/
│   ├── __init__.py
│   ├── generic_service.py      # 通用HTTP检测 + SSH命令启停（YAML即可扩展）
│   └── mineru_service.py       # Mineru 插件示例（文件上传检测）
├── templates/
│   └── index.html              # 运维界面模板
├── data/
│   ├── logs/                 # 运行日志
│   └── test.pdf              # 示例上传文件
├── docs/
│   └── project_context.md    # 本文档
├── main.py                   # 启动入口
└── requirements.txt
```

## 5. 执行与维护
- **启动**：
  - 安装依赖：`python -m pip install -r requirements.txt`
  - 启动前自检：`python doctor.py`
  - 运行：`python main.py`
  - 访问：`http://<监控机IP>:5000/`
- **新增服务（推荐：仅YAML）**：
  - 复制 [services_template.yaml](file:///d:/CODE/PyCODE/Heartbeat_Monitor/config/services_template.yaml) 为 `config/services/<你的服务>.yaml`
  - 填写 `category / test_api / expected_response`，并用 `on_failure` 选择失败策略（仅提示/自动重启）
  - 无需修改 `main.py`
- **新增服务（插件方式：适用于非标准API）**：
  - 新增 `services/<plugin>_service.py`，暴露 `create_service(service_id, cfg, config_path)` 工厂函数
  - 在对应 YAML 中填写 `plugin: "<plugin>"`
- **上下文维护**：任何需求变更或架构调整，需优先更新本文档。
