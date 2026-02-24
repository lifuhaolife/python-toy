# 运行所有测试
pytest tests/ -v

# 运行特定测试文件
pytest tests/test_database.py -v
pytest tests/test_connection_manager.py -v
pytest tests/test_metrics.py -v

# 运行并生成覆盖率报告
pytest tests/ -v --cov=../server --cov-report=html

# 运行测试并输出 XML 报告（用于 CI/CD）
pytest tests/ -v --junitxml=test-results.xml
