# 你的服务配置目录（自动加载）

程序只会加载本目录下的 `*.yaml/*.yml` 文件。

推荐做法：
- 从 `config/services_template.yaml` 或 `config/samples/` 复制一个样例到本目录
- 修改后把 `enabled` 设为 `true`

