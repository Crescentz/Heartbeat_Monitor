# 正式服务配置目录

程序只会自动加载本目录下的 `*.yaml` 和 `*.yml`。

## 建议用法
1. 从 `config/services_template.yaml` 或 `config/samples/` 复制一个样例到本目录。
2. 填写真实的 `id / name / host / test_api / expected_response`。
3. 默认建议把 `auto_check` 保持为 `false`，先确认检测口径、服务绑定和运维权限，再从页面开启自动检测。
4. 如果需要页面启停/重启，再补充 SSH 命令或 `plugin: localproc` 的本机运维配置。

## 说明
- `enabled: false` 的 YAML 不会被加载。
- 一个 YAML 可以包含一个服务，也可以包含 `services: [...]` 多个服务。
- 本目录建议只放真实内网配置，不要混放长期不用的演示样例。
