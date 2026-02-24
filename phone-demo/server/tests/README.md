# 单元测试文档

## 安装测试依赖

```bash
cd phone-demo/server
pip install -r tests/requirements-test.txt
```

## 运行测试

### 运行所有测试
```bash
pytest tests/ -v
```

### 运行特定测试文件
```bash
# 数据库测试
pytest tests/test_database.py -v

# 连接管理器测试
pytest tests/test_connection_manager.py -v

# 性能监控测试
pytest tests/test_metrics.py -v
```

### 生成覆盖率报告
```bash
# HTML 格式
pytest tests/ -v --cov=../server --cov-report=html

# 终端输出
pytest tests/ -v --cov=../server --cov-report=term
```

## 测试用例说明

### test_database.py - 数据库测试

| 测试方法 | 说明 |
|---------|------|
| `test_connect_sqlite` | 测试 SQLite 数据库连接 |
| `test_execute_query` | 测试 SQL 查询执行 |
| `test_load_from_env` | 测试从环境变量加载配置 |
| `test_print_config` | 测试配置打印功能 |

### test_connection_manager.py - WebSocket 连接管理器测试

| 测试方法 | 说明 |
|---------|------|
| `test_connect` | 测试新连接建立 |
| `test_disconnect` | 测试连接断开 |
| `test_send_bytes` | 测试二进制数据发送 |
| `test_send_json` | 测试 JSON 数据发送 |
| `test_send_to_disconnected` | 测试发送给已断开设备 |
| `test_max_connections` | 测试最大连接数限制 |
| `test_add_context` | 测试添加对话上下文 |
| `test_context_limit` | 测试上下文长度限制 |
| `test_get_stats` | 测试获取统计信息 |

### test_metrics.py - 性能监控测试

| 测试方法 | 说明 |
|---------|------|
| `test_record_request` | 测试请求记录 |
| `test_get_metrics` | 测试获取指标 |
| `test_ws_message_count` | 测试 WebSocket 消息计数 |
| `test_update_ws_connections` | 测试更新连接数 |
| `test_request_timer` | 测试请求计时器 |
| `test_request_timer_error` | 测试错误情况下的计时器 |
| `test_async_request_timer` | 测试异步请求计时器 |
| `test_async_request_timer_error` | 测试异步错误情况 |

## 测试结果

当前测试结果：**21 个测试全部通过** ✅

```
============================= 21 passed in 0.21s =============================
```

## 持续集成

测试已配置为在 CI/CD 流程中自动运行。测试结果将输出为 JUnit XML 格式：

```bash
pytest tests/ -v --junitxml=test-results.xml
```
