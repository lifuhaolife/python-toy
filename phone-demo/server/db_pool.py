"""
数据库连接池模块
优化数据库连接管理
"""
import asyncio
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager
import logging

from config import get_config, Config


class DatabasePool:
    """数据库连接池"""
    
    def __init__(self, config: Config):
        self.config = config
        self.db_type = config.DB_TYPE
        self._pool = None
        self._conn = None  # SQLite 使用单个连接
        self.logger = logging.getLogger("database")
        
    async def connect(self) -> None:
        """初始化数据库连接池"""
        if self.db_type == "mysql":
            await self._connect_mysql()
        else:
            await self._connect_sqlite()
    
    async def _connect_mysql(self) -> None:
        """连接 MySQL 数据库"""
        import aiomysql
        
        try:
            self._pool = await aiomysql.create_pool(
                host=self.config.MYSQL_HOST,
                port=self.config.MYSQL_PORT,
                user=self.config.MYSQL_USER,
                password=self.config.MYSQL_PASSWORD,
                db=self.config.MYSQL_DATABASE,
                autocommit=True,
                minsize=1,
                maxsize=self.config.MYSQL_POOL_SIZE,
                pool_recycle=3600,  # 1 小时回收连接
                pool_timeout=30,  # 连接超时
                connect_timeout=10,
                read_timeout=30,
                write_timeout=30,
                charset='utf8mb4'
            )
            
            # 测试连接
            async with self._pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("SELECT 1")
            
            self.logger.info(f"MySQL 连接池已创建 (大小：1-{self.config.MYSQL_POOL_SIZE})")
            
        except Exception as e:
            self.logger.error(f"MySQL 连接失败：{e}")
            raise
    
    async def _connect_sqlite(self) -> None:
        """连接 SQLite 数据库"""
        import aiosqlite
        
        try:
            self._conn = await aiosqlite.connect(self.config.SQLITE_DB_PATH)
            self._conn.row_factory = aiosqlite.Row
            
            # 启用外键
            await self._conn.execute("PRAGMA foreign_keys = ON")
            await self._conn.commit()
            
            # 设置 SQLite 优化参数
            await self._conn.execute("PRAGMA journal_mode = WAL")
            await self._conn.execute("PRAGMA synchronous = NORMAL")
            await self._conn.execute("PRAGMA cache_size = 10000")
            await self._conn.execute("PRAGMA temp_store = MEMORY")
            await self._conn.commit()
            
            self.logger.info(f"SQLite 数据库已连接：{self.config.SQLITE_DB_PATH}")
            
        except Exception as e:
            self.logger.error(f"SQLite 连接失败：{e}")
            raise
    
    async def close(self) -> None:
        """关闭数据库连接"""
        if self.db_type == "mysql":
            if self._pool:
                self._pool.close()
                await self._pool.wait_closed()
                self.logger.info("MySQL 连接池已关闭")
        else:
            if self._conn:
                await self._conn.close()
                self.logger.info("SQLite 连接已关闭")
    
    @asynccontextmanager
    async def acquire(self):
        """获取数据库连接"""
        if self.db_type == "mysql":
            async with self._pool.acquire() as conn:
                yield MySQLConnectionWrapper(conn)
        else:
            yield SQLiteConnectionWrapper(self._conn)
    
    async def execute(self, query: str, params: tuple = None) -> 'CursorWrapper':
        """执行 SQL 查询"""
        if self.db_type == "mysql":
            async with self._pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(query, params or ())
                    return CursorWrapper(cursor, 'mysql')
        else:
            cursor = await self._conn.execute(query, params or ())
            return CursorWrapper(cursor, 'sqlite')
    
    async def commit(self) -> None:
        """提交事务"""
        if self.db_type == "sqlite" and self._conn:
            await self._conn.commit()
    
    def get_pool_stats(self) -> Dict[str, Any]:
        """获取连接池统计信息"""
        if self.db_type == "mysql" and self._pool:
            return {
                'type': 'mysql',
                'size': self._pool.maxsize,
                'free': self._pool.freesize,
                'used': self._pool.maxsize - self._pool.freesize,
            }
        else:
            return {
                'type': 'sqlite',
                'connected': self._conn is not None and not self._conn.closed,
            }


class CursorWrapper:
    """游标包装器"""
    
    def __init__(self, cursor, db_type: str):
        self.cursor = cursor
        self.db_type = db_type
    
    async def fetchone(self) -> Optional[Dict[str, Any]]:
        """获取一行"""
        if self.db_type == 'mysql':
            row = await self.cursor.fetchone()
            if row:
                return dict(zip([d[0] for d in self.cursor.description], row))
            return None
        else:
            return await self.cursor.fetchone()
    
    async def fetchall(self) -> List[Dict[str, Any]]:
        """获取所有行"""
        if self.db_type == 'mysql':
            rows = await self.cursor.fetchall()
            return [dict(zip([d[0] for d in self.cursor.description], row)) for row in rows]
        else:
            return await self.cursor.fetchall()
    
    @property
    def rowcount(self) -> int:
        """获取影响行数"""
        return self.cursor.rowcount
    
    @property
    def lastrowid(self) -> int:
        """获取最后插入的 ID"""
        return self.cursor.lastrowid


class MySQLConnectionWrapper:
    """MySQL 连接包装器"""
    
    def __init__(self, conn):
        self.conn = conn
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass
    
    async def execute(self, query: str, params: tuple = None):
        async with self.conn.cursor() as cursor:
            await cursor.execute(query, params or ())
            return CursorWrapper(cursor, 'mysql')


class SQLiteConnectionWrapper:
    """SQLite 连接包装器"""
    
    def __init__(self, conn):
        self.conn = conn
    
    async def execute(self, query: str, params: tuple = None):
        cursor = await self.conn.execute(query, params or ())
        return CursorWrapper(cursor, 'sqlite')
    
    async def commit(self):
        await self.conn.commit()


# 全局数据库池实例
_db_pool: Optional[DatabasePool] = None


def get_database_pool() -> DatabasePool:
    """获取数据库连接池实例"""
    global _db_pool
    if _db_pool is None:
        config = get_config()
        _db_pool = DatabasePool(config)
    return _db_pool
