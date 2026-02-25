# 扩展开发（插件规范）

当仅靠 YAML 无法描述检测逻辑时（例如：签名鉴权、分步调用、需要解析复杂返回、上传文件且需深度校验），使用插件方式扩展。

## 1. 插件文件命名约定
- YAML：`plugin: "<plugin>"`
- 插件文件：`services/<plugin>_service.py`

例如：
- `plugin: "mineru"`
- 文件：[mineru_service.py](file:///d:/CODE/PyCODE/Heartbeat_Monitor/services/mineru_service.py)

## 2. 插件必须暴露工厂函数
插件模块内必须提供：
```python
def create_service(service_id: str, cfg: dict, config_path: str):
    ...
```

系统会通过 [service_loader.py](file:///d:/CODE/PyCODE/Heartbeat_Monitor/core/service_loader.py) 动态加载并调用该工厂函数。

## 3. 服务对象接口
插件服务对象需继承 [BaseService](file:///d:/CODE/PyCODE/Heartbeat_Monitor/core/base_service.py)，并实现：
- `check_health() -> (ok, message, detail)`
  - ok：bool
  - message：失败原因（会写入错误日志）
  - detail：dict，建议包含 `status_code/elapsed_ms/response_excerpt` 等，便于页面展示与排障
- `start_service()/stop_service()/restart_service() -> (ok, message)`

## 4. 常用实现建议
- 检测尽量返回结构化 detail，便于在 Web “服务详情”中排错
- 启停尽量用 `restart_cmds`（多条命令）描述完整恢复链路
- 单个插件不要依赖全局变量，不要在 import 阶段做网络/SSH调用

