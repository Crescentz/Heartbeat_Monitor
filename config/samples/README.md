# 样例配置目录

本目录仅存放参考样例，不会被程序自动加载。

## 使用方式
1. 选择一个最接近你场景的样例。
2. 复制到 `config/services/`。
3. 修改为真实内网地址、检测接口和运维命令。
4. 再把 `enabled` 改为 `true`。

## 样例选择建议
- `api_only_sample.yaml`
  - 只做 HTTP/API 监控，不提供启停能力。
- `web_only_sample.yaml`
  - 只看网页可达性或关键字。
- `local_restart_demo.yaml`
  - 本机自动重启演示。
- `local_test_managed.yaml`
  - 本机启停演示。
- `example_service.yaml`
  - 远端 SSH 命令与脚本式启停演示。
- `mineru.yaml`
  - 文件上传检测插件样例。
