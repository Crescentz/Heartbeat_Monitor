# 开发与回归脚本说明

本目录存放可选的开发辅助脚本、接口验证脚本和回归脚本，不参与主程序运行。

主程序入口仍然是 `main.py`。如果你只是部署和使用系统，可以忽略本目录。

## 推荐执行顺序
1. `python doctor.py`
2. `python archive/dev_tools/__verify_home.py`
3. `python archive/dev_tools/__verify_disabled_api.py`
4. `python archive/dev_tools/__e2e_admin_common_ops.py`

## 脚本说明
- `__verify_home.py`
  - 最小化检查首页和 Flask 路由是否可创建。
- `__verify_disabled_api.py`
  - 验证管理员禁用/启用服务接口与运行时状态同步。
- `__e2e_admin_common_ops.py`
  - 管理员常用操作回归脚本。
  - 覆盖：启停、立即检测、自动检测开关、自动重启开关、服务禁用、用户绑定。
  - 使用 Flask `test_client` 和本地专用 fixture，自带现场清理，适合反复执行。
- `_admin_ops_fixture.py`
  - 仅供 `__e2e_admin_common_ops.py` 调用的本地样例服务。
- `__e2e_web_smoke.py`
  - 针对已启动 Web 服务的轻量冒烟脚本。
- `__e2e_failure_policy.py`
  - 验证失败策略切换接口。
- `__e2e_disable_test.py`
  - 验证禁用服务后的接口行为。
- `__e2e_auto_restart_delay_check.py`
  - 验证自动重启后的延迟复检逻辑。
- `__e2e_local_restart_demo_start_fix.py`
  - 验证本机重启样例在“已运行时点击启动”场景下走重启逻辑。
- `__e2e_admin_ping.py`
  - 检查登录态与管理员接口访问。
- `__print_routes.py`
  - 打印当前 Flask 路由，便于定位接口。
- `__check_services.py`
  - 辅助查看服务加载与静态检查结果。
- `probe_local_restart_api.py`
  - 手工探测 `local_restart_demo` 样例接口。

## 说明
- 新增回归脚本优先使用 `Flask test_client`，减少对本机端口和外部环境的依赖。
- 需要真实浏览器或真实已启动服务时，再补充单独的 E2E 脚本。
