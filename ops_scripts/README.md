# 运维脚本目录（可选）

用于存放某个服务的复杂启停/重启脚本文件，配合 YAML 的 `@script:` 语法使用（兼容 `script:`，但推荐统一写 `@script:`）。

## 目录建议

每个服务一个子目录：

- `ops_scripts/<service_id>/start.sh`
- `ops_scripts/<service_id>/stop.sh`
- `ops_scripts/<service_id>/restart.sh`

脚本内容建议：

- 使用 `bash` 语法（远端将用 `bash <脚本>` 执行）
- 严禁在脚本里写明文密码/密钥
- 出错时 `exit 1`，成功 `exit 0`

## YAML 写法

在对应服务 YAML 里配置：

- `start_cmds:` 里写 `@script:ops_scripts/<service_id>/start.sh`
- `stop_cmds:` 里写 `@script:ops_scripts/<service_id>/stop.sh`
- `restart_cmds:` 里写 `@script:ops_scripts/<service_id>/restart.sh`

