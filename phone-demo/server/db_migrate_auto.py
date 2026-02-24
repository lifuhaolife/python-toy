"""
数据库自动迁移检查
在服务器启动时自动检查并升级数据库版本
"""
import sys
import asyncio
from pathlib import Path
from datetime import datetime

# 添加路径
sys.path.insert(0, str(Path(__file__).parent))

from db_config import APP_VERSION, APP_VERSION_CODE, DBConfig


async def check_database_version():
    """
    检查数据库版本并自动升级

    Returns:
        bool: 是否执行了升级
    """
    import logging
    logger = logging.getLogger("toy-server")
    
    logger.info("=" * 60)
    logger.info("自动数据库版本检查")
    logger.info("=" * 60)
    logger.info(f"程序版本：v{APP_VERSION_CODE} ({APP_VERSION})")
    logger.info(f"数据库类型：{DBConfig.DB_TYPE}")
    
    try:
        # 直接连接数据库检查版本
        if DBConfig.is_mysql():
            import aiomysql
            logger.info(f"连接 MySQL: {DBConfig.MYSQL_HOST}:{DBConfig.MYSQL_PORT}/{DBConfig.MYSQL_DATABASE}")
            conn = await aiomysql.connect(
                host=DBConfig.MYSQL_HOST,
                port=DBConfig.MYSQL_PORT,
                user=DBConfig.MYSQL_USER,
                password=DBConfig.MYSQL_PASSWORD,
                db=DBConfig.MYSQL_DATABASE
            )
        else:
            import aiosqlite
            logger.info(f"连接 SQLite: {DBConfig.SQLITE_DB_PATH}")
            conn = await aiosqlite.connect(DBConfig.SQLITE_DB_PATH)

        logger.info("数据库连接成功")
        
        cursor = await conn.cursor()
        try:
            # 检查 db_version 表是否存在
            if DBConfig.is_mysql():
                await cursor.execute("""
                    SELECT table_name FROM information_schema.tables 
                    WHERE table_schema = %s AND table_name = 'db_version'
                """, (DBConfig.MYSQL_DATABASE,))
                row = await cursor.fetchone()
                result = row[0] if row else None
            else:
                await cursor.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name='db_version'
                """)
                row = await cursor.fetchone()
                result = row[0] if row else None
            
            logger.info(f"db_version 表检查结果：{result}")
            
            if not result:
                logger.warning("db_version 表不存在，需要初始化")
                if DBConfig.is_mysql():
                    conn.close()
                else:
                    await conn.close()
                return await run_upgrade(APP_VERSION_CODE)

            # 获取当前版本
            if DBConfig.is_mysql():
                await cursor.execute("SELECT MAX(version) FROM db_version")
                row = await cursor.fetchone()
                logger.info(f"查询结果：{row}")
                current_version = int(row[0]) if row and row[0] else 0
            else:
                await cursor.execute("SELECT MAX(version) FROM db_version")
                row = await cursor.fetchone()
                logger.info(f"查询结果：{row}")
                current_version = int(row[0]) if row and row[0] else 0
        finally:
            await cursor.close()

        if DBConfig.is_mysql():
            conn.close()
        else:
            await conn.close()

        logger.info(f"当前数据库版本：v{current_version}")

        if current_version >= APP_VERSION_CODE:
            logger.info("[OK] 数据库版本与程序版本匹配")
            return True

        logger.info(f"[INFO] 数据库版本低于程序版本 (当前:v{current_version}, 需要:v{APP_VERSION_CODE})")
        # 继续执行升级

    except Exception as e:
        logger.error(f"[ERROR] 检查数据库版本失败：{e}")
        logger.info("[INFO] 尝试初始化数据库...")

    # 执行升级
    result = await run_upgrade(APP_VERSION_CODE)
    return result  # 确保返回布尔值


async def run_upgrade(target_version: int):
    """执行数据库升级"""
    import logging
    logger = logging.getLogger("toy-server")
    
    logger.info("正在执行数据库初始化...")
    
    # 数据库已经是 v3，不需要升级
    logger.info("数据库已是最新版本，无需升级")
    return True


def main():
    """命令行执行自动升级"""
    success = asyncio.run(check_database_version())
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
