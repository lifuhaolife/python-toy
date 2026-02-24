"""
单元测试 - 数据库连接池
"""
import pytest
import asyncio
import sys
import os

# 添加路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'server'))

from db_pool import DatabasePool, get_database_pool
from config import Config


class TestDatabasePool:
    """数据库连接池测试"""
    
    @pytest.fixture
    def config(self):
        """测试配置"""
        config = Config()
        config.DB_TYPE = "sqlite"
        config.SQLITE_DB_PATH = ":memory:"
        return config
    
    @pytest.fixture
    def pool(self, config):
        """连接池实例"""
        pool = DatabasePool(config)
        return pool
    
    @pytest.mark.asyncio
    async def test_connect_sqlite(self, pool):
        """测试 SQLite 连接"""
        await pool.connect()
        assert pool._conn is not None
        await pool.close()
    
    @pytest.mark.asyncio
    async def test_execute_query(self, pool):
        """测试执行查询"""
        await pool.connect()
        
        # 创建测试表
        await pool.execute("""
            CREATE TABLE IF NOT EXISTS test_table (
                id INTEGER PRIMARY KEY,
                name TEXT
            )
        """)
        await pool.commit()
        
        # 插入数据
        await pool.execute(
            "INSERT INTO test_table (name) VALUES (?)",
            ("test",)
        )
        await pool.commit()
        
        # 查询数据
        cursor = await pool.execute("SELECT * FROM test_table")
        rows = await cursor.fetchall()
        
        assert len(rows) == 1
        assert rows[0]['name'] == 'test'
        
        await pool.close()


class TestConfig:
    """配置测试"""
    
    def test_load_from_env(self):
        """测试从环境变量加载配置"""
        config = Config()
        config.load_from_env()
        
        assert config.HOST is not None
        assert config.PORT > 0
    
    def test_print_config(self, caplog):
        """测试打印配置"""
        import logging
        config = Config()
        config.load_from_env()
        
        logger = logging.getLogger("config")
        config.print_config()
        
        assert "应用配置" in caplog.text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
