"""
日志系统模块
提供结构化的日志记录功能
"""
import os
import sys
import logging
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from datetime import datetime
from pathlib import Path
from typing import Optional


class LogFormatter(logging.Formatter):
    """自定义日志格式"""
    
    # 彩色输出（仅终端）
    COLORS = {
        'DEBUG': '\033[36m',     # 青色
        'INFO': '\033[32m',      # 绿色
        'WARNING': '\033[33m',   # 黄色
        'ERROR': '\033[31m',     # 红色
        'CRITICAL': '\033[35m',  # 紫色
    }
    RESET = '\033[0m'
    
    def __init__(self, use_color: bool = False):
        super().__init__()
        self.use_color = use_color
        self.format_str = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        self.date_format = '%Y-%m-%d %H:%M:%S'
        
        # 设置格式
        formatter = logging.Formatter(self.format_str, datefmt=self.date_format)
        self._formatter = formatter
    
    def format(self, record: logging.LogRecord) -> str:
        # 添加颜色
        if self.use_color and record.levelname in self.COLORS:
            record.levelname = f"{self.COLORS[record.levelname]}{record.levelname}{self.RESET}"
        return self._formatter.format(record)


def setup_logger(
    name: str,
    log_dir: Optional[str] = None,
    level: str = "INFO",
    console_output: bool = True,
    file_output: bool = True,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 10,
    use_color: bool = True
) -> logging.Logger:
    """
    设置日志记录器
    
    Args:
        name: 日志名称
        log_dir: 日志文件目录
        level: 日志级别
        console_output: 是否输出到控制台
        file_output: 是否输出到文件
        max_bytes: 单个日志文件最大大小
        backup_count: 保留的日志文件数量
        use_color: 是否使用彩色输出
    
    Returns:
        配置好的 logger 实例
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))
    
    # 清除现有 handler
    logger.handlers.clear()
    
    # 控制台 handler
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, level.upper()))
        
        # 检测是否为终端
        is_terminal = sys.stdout.isatty()
        console_formatter = LogFormatter(use_color=use_color and is_terminal)
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
    
    # 文件 handler
    if file_output and log_dir:
        os.makedirs(log_dir, exist_ok=True)
        
        # 按时间分割的日志文件
        log_filename = datetime.now().strftime(f'{name}_%Y%m%d_%H%M%S.log')
        log_filepath = os.path.join(log_dir, log_filename)
        
        # 使用按大小分割的 RotatingFileHandler
        file_handler = RotatingFileHandler(
            log_filepath,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(getattr(logging, level.upper()))
        
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
        
        # 保存当前日志文件路径
        logger.info(f"日志文件：{log_filepath}")
    
    return logger


def get_logger(name: str) -> logging.Logger:
    """获取已存在的 logger"""
    return logging.getLogger(name)


class PerformanceLogger:
    """性能日志记录器"""
    
    def __init__(self, logger: logging.Logger, operation: str):
        self.logger = logger
        self.operation = operation
        self.start_time: Optional[datetime] = None
    
    def __enter__(self):
        self.start_time = datetime.now()
        self.logger.info(f"[PERF] 开始：{self.operation}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            duration = (datetime.now() - self.start_time).total_seconds() * 1000
            if exc_type:
                self.logger.error(f"[PERF] 失败：{self.operation} - 耗时：{duration:.2f}ms - 错误：{exc_val}")
            else:
                self.logger.info(f"[PERF] 完成：{self.operation} - 耗时：{duration:.2f}ms")
        return False


class RequestContextFilter(logging.Filter):
    """请求上下文过滤器 - 添加请求追踪 ID"""
    
    def __init__(self, request_id: str):
        super().__init__()
        self.request_id = request_id
    
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = self.request_id
        return True


def create_request_logger(base_logger: logging.Logger, request_id: str) -> logging.Logger:
    """创建带请求 ID 的日志记录器"""
    request_logger = logging.getLogger(f"{base_logger.name}.{request_id}")
    request_logger.handlers = base_logger.handlers.copy()
    
    # 添加请求 ID 过滤器
    request_logger.addFilter(RequestContextFilter(request_id))
    
    # 修改格式以包含请求 ID
    for handler in request_logger.handlers:
        handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - [%(request_id)s] - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        ))
    
    return request_logger
