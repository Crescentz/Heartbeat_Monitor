# Heartbeat Monitor

一个面向内网场景的服务心跳检测与运维面板。

典型部署方式：
- 程序部署在服务器 A。
- 由 A 定时检测 A、B、C、D 等服务器上的服务。
- 通过浏览器访问 A 的 Web 页面查看状态、日志和管理员开关。

## 主要能力
- HTTP/HTTPS 健康检查
- 文件上传类业务检测
- 远端 SSH 启停/重启
- 本机 `localproc` 启停/重启
- 自动检测开关与频率配置
- 失败策略切换：仅提示 / 自动重启
- 服务禁用 / 启用
- 用户管理与服务绑定

## 快速开始
```powershell
python -m pip install -r requirements.txt
python doctor.py
python main.py
```

默认访问地址：
- `http://127.0.0.1:60005/`

可用环境变量：
- `HBM_HOST`
- `HBM_PORT`
- `HBM_DEBUG`

首次启动会自动创建默认管理员账号：
- `admin / admin`

## 配置方式
- 正式配置目录：`config/services/`
- 样例目录：`config/samples/`
- 模板文件：`config/services_template.yaml`

建议流程：
1. 从模板或样例复制一个 YAML 到 `config/services/`。
2. 填写真实的 `id / name / host / test_api / expected_response`。
3. 默认先保持 `auto_check: false`。
4. 如需启停/重启，再补 SSH 命令或 `plugin: localproc`。
5. 启动后由管理员在页面开启自动检测和绑定用户。

## 目录说明
- `main.py`
  - 启动入口。
- `monitor/webapp.py`
  - Flask Web 应用与管理员接口。
- `templates/`
  - 前端页面模板。
- `core/`
  - 调度、日志、权限、状态存储、运行时状态收敛。
- `services/`
  - 通用服务与插件实现。
- `config/services/`
  - 正式服务配置。
- `config/samples/`
  - 参考样例。
- `archive/dev_tools/`
  - 开发辅助与回归脚本。
- `docs/`
  - 使用说明、配置参考、架构和变更记录。

## 当前运行逻辑
- 页面显示和调度器执行共用 `core/runtime_state.py` 的状态补齐逻辑。
- `auto_check`、`ops_enabled`、`disabled`、`on_failure` 都会在启动时从 YAML 与持久化文件统一收敛。
- 新纳管服务若未显式填写 `auto_check`，默认先不参与定时检测。
- 是否允许启停/重启由 `ops_enabled` 控制。
- 是否在检测失败后自动重启由 `on_failure` 控制。

## 常用验证
```powershell
python archive/dev_tools/__verify_home.py
python archive/dev_tools/__verify_disabled_api.py
python archive/dev_tools/__e2e_admin_common_ops.py
```

`__e2e_admin_common_ops.py` 会覆盖：
- 启动 / 停止 / 立即检测
- 自动检测开关
- 自动重启开关
- 服务禁用 / 启用
- 用户绑定

## 文档
- `docs/user_guide.md`
- `docs/config_reference.md`
- `docs/architecture.md`
- `docs/maintainer_guide.md`
- `docs/changelog.md`
- `docs/project_context.md`
