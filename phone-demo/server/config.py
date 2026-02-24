"""
配置管理模块
统一管理所有配置项
"""
import os
from pathlib import Path
from typing import Optional


class Config:
    """应用配置"""
    
    # 基础配置
    BASE_DIR = Path(__file__).parent.parent
    ENV_FILE = BASE_DIR / ".env"
    
    # 服务器配置
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = False
    
    # WebSocket 配置
    WS_HEARTBEAT_INTERVAL: int = 30  # 心跳间隔（秒）
    WS_RECEIVE_TIMEOUT: int = 60  # 接收超时（秒）
    WS_MAX_MESSAGE_SIZE: int = 1024 * 1024  # 最大消息大小（1MB）
    
    # 音频配置
    SAMPLE_RATE: int = 16000
    CHANNELS: int = 1
    CHUNK_SIZE: int = 1024
    MIN_AUDIO_DURATION: float = 1.0  # 最小音频时长（秒）
    
    # AI 配置
    AI_API_KEY: str = ""
    AI_API_BASE_URL: str = "https://open.bigmodel.cn/api/paas/v4"
    AI_MODEL: str = "glm-4"
    AI_MAX_TOKENS: int = 150
    AI_TEMPERATURE: float = 0.7
    AI_TIMEOUT: int = 60  # AI 请求超时（秒）
    
    # 数据库配置
    DB_TYPE: str = "sqlite"  # sqlite 或 mysql
    MYSQL_HOST: str = "localhost"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "root"
    MYSQL_PASSWORD: str = ""
    MYSQL_DATABASE: str = "toy_db"
    MYSQL_POOL_SIZE: int = 5
    MYSQL_MAX_OVERFLOW: int = 10
    SQLITE_DB_PATH: str = ""
    
    # 日志配置
    LOG_LEVEL: str = "INFO"
    LOG_DIR: str = ""
    LOG_MAX_BYTES: int = 10 * 1024 * 1024  # 10MB
    LOG_BACKUP_COUNT: int = 10
    
    # 记忆管理配置
    MEMORY_MAX_SHORT_TERM: int = 10  # 短期记忆最大轮数
    MEMORY_SUMMARY_ENABLED: bool = True
    
    # 性能配置
    MAX_CONCURRENT_REQUESTS: int = 10  # 最大并发请求数
    REQUEST_QUEUE_SIZE: int = 100  # 请求队列大小
    
    _initialized = False
    
    @classmethod
    def load_from_env(cls) -> None:
        """从环境变量加载配置"""
        if cls._initialized:
            return
        
        # 加载 .env 文件
        if cls.ENV_FILE.exists():
            from dotenv import load_dotenv
            load_dotenv(cls.ENV_FILE)
        
        # 服务器配置
        cls.HOST = os.getenv("HOST", cls.HOST)
        cls.PORT = int(os.getenv("PORT", cls.PORT))
        cls.DEBUG = os.getenv("DEBUG", "false").lower() == "true"
        
        # WebSocket 配置
        cls.WS_HEARTBEAT_INTERVAL = int(os.getenv("WS_HEARTBEAT_INTERVAL", cls.WS_HEARTBEAT_INTERVAL))
        cls.WS_RECEIVE_TIMEOUT = int(os.getenv("WS_RECEIVE_TIMEOUT", cls.WS_RECEIVE_TIMEOUT))
        
        # AI 配置
        cls.AI_API_KEY = os.getenv("AI_API_KEY", cls.AI_API_KEY)
        cls.AI_API_BASE_URL = os.getenv("AI_API_BASE_URL", cls.AI_API_BASE_URL)
        cls.AI_MODEL = os.getenv("AI_MODEL", cls.AI_MODEL)
        cls.AI_MAX_TOKENS = int(os.getenv("AI_MAX_TOKENS", cls.AI_MAX_TOKENS))
        cls.AI_TEMPERATURE = float(os.getenv("AI_TEMPERATURE", cls.AI_TEMPERATURE))
        cls.AI_TIMEOUT = int(os.getenv("AI_TIMEOUT", cls.AI_TIMEOUT))
        
        # 数据库配置
        cls.DB_TYPE = os.getenv("DB_TYPE", cls.DB_TYPE).lower()
        cls.MYSQL_HOST = os.getenv("MYSQL_HOST", cls.MYSQL_HOST)
        cls.MYSQL_PORT = int(os.getenv("MYSQL_PORT", cls.MYSQL_PORT))
        cls.MYSQL_USER = os.getenv("MYSQL_USER", cls.MYSQL_USER)
        cls.MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", cls.MYSQL_PASSWORD)
        cls.MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", cls.MYSQL_DATABASE)
        cls.MYSQL_POOL_SIZE = int(os.getenv("MYSQL_POOL_SIZE", cls.MYSQL_POOL_SIZE))
        cls.MYSQL_MAX_OVERFLOW = int(os.getenv("MYSQL_MAX_OVERFLOW", cls.MYSQL_MAX_OVERFLOW))
        cls.SQLITE_DB_PATH = os.getenv("SQLITE_DB_PATH", str(cls.BASE_DIR / "server" / "toy.db"))
        
        # 日志配置
        cls.LOG_LEVEL = os.getenv("LOG_LEVEL", cls.LOG_LEVEL)
        cls.LOG_DIR = os.getenv("LOG_DIR", str(cls.BASE_DIR / "server" / "logs"))
        
        # 记忆管理配置
        cls.MEMORY_MAX_SHORT_TERM = int(os.getenv("MEMORY_MAX_SHORT_TERM", cls.MEMORY_MAX_SHORT_TERM))
        cls.MEMORY_SUMMARY_ENABLED = os.getenv("MEMORY_SUMMARY_ENABLED", "true").lower() == "true"
        
        # 性能配置
        cls.MAX_CONCURRENT_REQUESTS = int(os.getenv("MAX_CONCURRENT_REQUESTS", cls.MAX_CONCURRENT_REQUESTS))
        cls.REQUEST_QUEUE_SIZE = int(os.getenv("REQUEST_QUEUE_SIZE", cls.REQUEST_QUEUE_SIZE))
        
        cls._initialized = True
    
    @classmethod
    def print_config(cls) -> None:
        """打印配置信息（隐藏敏感信息）"""
        import logging
        logger = logging.getLogger("config")
        
        logger.info("=" * 60)
        logger.info("应用配置")
        logger.info("=" * 60)
        logger.info(f"运行模式：{'DEBUG' if cls.DEBUG else 'PRODUCTION'}")
        logger.info(f"服务器地址：{cls.HOST}:{cls.PORT}")
        logger.info(f"数据库类型：{cls.DB_TYPE}")
        if cls.DB_TYPE == "mysql":
            logger.info(f"MySQL 连接：{cls.MYSQL_HOST}:{cls.MYSQL_PORT}/{cls.MYSQL_DATABASE}")
            logger.info(f"MySQL 连接池大小：{cls.MYSQL_POOL_SIZE}")
        else:
            logger.info(f"SQLite 路径：{cls.SQLITE_DB_PATH}")
        logger.info(f"AI 模型：{cls.AI_MODEL}")
        logger.info(f"AI API Key: {cls.AI_API_KEY[:10]}...{cls.AI_API_KEY[-6:]}" if len(cls.AI_API_KEY) > 20 else f"AI API Key: ***")
        logger.info(f"最大并发请求：{cls.MAX_CONCURRENT_REQUESTS}")
        logger.info("=" * 60)


# 全局配置实例
config = Config()


def get_config() -> Config:
    """获取配置实例"""
    if not config._initialized:
        config.load_from_env()
    return config
