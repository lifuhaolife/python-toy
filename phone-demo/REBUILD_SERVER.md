# 重构后代码说明

## 服务器版本：v3.0.0-rebuild

### 核心模块

| 模块 | 说明 | 行数 |
|------|------|------|
| `server.py` | 主服务器文件（重构版） | ~820 |
| `asr_client.py` | 优化的语音识别客户端 | ~320 |
| `config.py` | 统一配置管理 | ~150 |
| `logger.py` | 结构化日志系统 | ~180 |
| `db_pool.py` | 数据库连接池 | ~200 |
| `metrics.py` | 性能监控模块 | ~220 |
| `database.py` | 数据库操作层 | ~780 |
| `memory_manager.py` | 记忆管理器 | ~350 |

### 主要改进

#### 1. 配置管理 (`config.py`)
```python
from config import get_config

config = get_config()
print(config.HOST, config.PORT)
```

**功能:**
- 统一环境变量加载
- 支持 MySQL 和 SQLite
- 可配置的 WebSocket、AI、数据库参数

#### 2. 日志系统 (`logger.py`)
```python
from logger import setup_logger

logger = setup_logger(
    name="my-app",
    log_dir="./logs",
    level="INFO"
)
```

**功能:**
- 彩色控制台输出
- 按大小轮转的日志文件
- 性能日志记录器
- 请求上下文追踪

#### 3. 数据库连接池 (`db_pool.py`)
```python
from db_pool import get_database_pool

pool = get_database_pool()
await pool.connect()

# 执行查询
cursor = await pool.execute("SELECT * FROM table")
```

**MySQL 连接池配置:**
- 最小连接：1
- 最大连接：5
- 连接回收：3600 秒
- 超时：30 秒

**SQLite 优化:**
- WAL 模式
- 同步模式：NORMAL
- 缓存大小：10000

#### 4. 性能监控 (`metrics.py`)
```python
from metrics import get_metrics_collector, AsyncRequestTimer

metrics = get_metrics_collector()

# 记录请求延迟
async with AsyncRequestTimer("operation"):
    await do_something()

# 获取指标
stats = metrics.get_metrics()
```

**监控指标:**
- 请求延迟 (avg, p95, p99)
- 请求速率
- 错误率
- WebSocket 连接数
- CPU/内存使用率

**API 端点:**
- `GET /health` - 健康检查
- `GET /metrics` - 性能指标

#### 5. 优化的 ASR (`asr_client.py`)
```python
from asr_client import get_asr_client

asr = get_asr_client()
text = asr.transcribe(audio_data)
```

**改进:**
- 音频预处理（降噪、增益、限幅）
- VAD 参数优化（阈值 0.6，静音 300ms）
- 识别参数优化（beam_size=5, best_of=5）
- 繁体转简体
- 文本后处理

#### 6. WebSocket 连接管理
```python
from server import ConnectionManager

manager = ConnectionManager(max_connections=100)

# 连接
await manager.connect(ws, device_id)

# 发送
await manager.send_bytes(device_id, data)
await manager.send_json(device_id, {"type": "response"})

# 断开
manager.disconnect(device_id)
```

**改进:**
- 最大连接数限制 (100)
- 连接状态预检查
- 自动清理断开连接
- 并发信号量控制

### 启动服务器

```bash
cd phone-demo/server
python server.py
```

**启动日志示例:**
```
2026-02-24 21:49:57 - toy-server - INFO - 儿童智能语音玩具服务器 v3.0.0-rebuild
2026-02-24 21:49:57 - toy-server - INFO - 初始化数据库连接池...
2026-02-24 21:49:57 - toy-server - INFO - MySQL 连接池已创建 (大小：1-5)
2026-02-24 21:49:57 - toy-server - INFO - 初始化 AI 客户端...
2026-02-24 21:49:57 - toy-server - INFO - 初始化 TTS 客户端...
2026-02-24 21:49:57 - toy-server - INFO - 初始化 ASR 客户端...
2026-02-24 21:49:57 - toy-server - INFO - Whisper 模型加载成功
2026-02-24 21:49:57 - toy-server - INFO - 初始化记忆管理器...
2026-02-24 21:49:57 - toy-server - INFO - 初始化性能监控...
2026-02-24 21:49:57 - toy-server - INFO - 性能监控已启动
2026-02-24 21:49:57 - toy-server - INFO - 服务器地址：http://0.0.0.0:8000
2026-02-24 21:49:57 - toy-server - INFO - 最大连接数：100
2026-02-24 21:49:57 - toy-server - INFO - 最大并发请求：10
```

### 测试方法

#### 单元测试
```bash
cd phone-demo/server
pip install -r tests/requirements-test.txt
pytest tests/ -v
```

**测试覆盖:**
- `test_database.py` - 数据库测试 (4 用例)
- `test_connection_manager.py` - WebSocket 管理器 (9 用例)
- `test_metrics.py` - 性能监控 (8 用例)

**总计:** 21 个测试全部通过 ✅

#### ASR 测试
```bash
cd phone-demo/server
python test_asr.py
```

**测试内容:**
- 音频预处理测试
- 语音识别测试

#### 繁体转简体测试
```bash
cd phone-demo/server
python test_traditional_to_simplified.py
```

**测试覆盖:** 20/20 通过 ✅

#### 自动化测试
```bash
cd phone-demo
python test_app_automation.py
```

**测试流程:**
1. 自动连接服务器
2. 发送模拟音频
3. 等待并分析响应
4. 自动断开连接

### 监控端点

#### 健康检查
```bash
curl http://localhost:8000/health
```

**响应:**
```json
{
  "status": "healthy",
  "connections": 0,
  "max_connections": 100,
  "database": {
    "type": "mysql",
    "size": 5,
    "free": 5,
    "used": 0
  },
  "timestamp": "2026-02-24T21:49:57"
}
```

#### 性能指标
```bash
curl http://localhost:8000/metrics
```

**响应:**
```json
{
  "timestamp": "2026-02-24T21:49:57",
  "uptime_seconds": 60,
  "latency_avg_ms": 150.5,
  "latency_p95_ms": 200.0,
  "latency_p99_ms": 250.0,
  "requests_per_minute": 10,
  "error_rate_percent": 0.5,
  "websocket_connections": 1,
  "cpu_percent": 15.2,
  "memory_mb": 256.8
}
```

### 配置说明

编辑 `.env` 文件：

```bash
# 服务器配置
HOST=0.0.0.0
PORT=8000
DEBUG=false

# 数据库配置
DB_TYPE=mysql
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=toy_db
MYSQL_POOL_SIZE=5

# AI 配置
AI_API_KEY=your_api_key
AI_MODEL=glm-4
AI_TIMEOUT=60

# 日志配置
LOG_LEVEL=INFO
LOG_DIR=./logs

# 性能配置
MAX_CONCURRENT_REQUESTS=10
WS_HEARTBEAT_INTERVAL=30
```

### 故障排查

#### 问题 1: 服务器启动失败

**检查日志:**
```bash
cd phone-demo/server
dir /b /o-d logs | findstr /n "." | findstr "^1:"
type logs\最新日志文件
```

**常见原因:**
- 数据库连接失败
- 端口被占用
- 模型文件缺失

#### 问题 2: ASR 识别失败

**检查模型:**
```bash
dir models\whisper-tiny
```

**重新下载模型:**
```bash
python download_whisper_model.py
```

#### 问题 3: 连接数过多

**查看监控:**
```bash
curl http://localhost:8000/metrics | findstr "websocket_connections"
```

**调整最大连接数:**
在 `server.py` 中修改：
```python
manager = ConnectionManager(max_connections=200)  # 增加上限
```

### 总结

重构后的服务器 v3.0.0-rebuild 具有以下特点：

1. **模块化设计** - 各功能独立模块，易于维护
2. **性能优化** - 连接池、缓存、并发控制
3. **监控完善** - 实时指标、健康检查、日志轮转
4. **错误处理** - 完善的异常捕获和恢复机制
5. **测试覆盖** - 21 个单元测试 + 自动化测试
6. **中文支持** - 繁体转简体、语音识别优化

所有代码已推送到远程仓库，可以直接使用。✅
