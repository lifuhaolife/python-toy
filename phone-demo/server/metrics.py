"""
性能监控模块
监控系统性能和资源使用
"""
import asyncio
import time
import psutil
from datetime import datetime
from typing import Dict, Any, Optional
from collections import deque
import logging


class MetricsCollector:
    """指标收集器"""
    
    def __init__(self, max_samples: int = 1000):
        self.max_samples = max_samples
        self.logger = logging.getLogger("metrics")
        
        # 请求指标
        self.request_latencies = deque(maxlen=max_samples)  # 请求延迟
        self.request_counts = deque(maxlen=max_samples)  # 请求计数
        self.error_counts = deque(maxlen=max_samples)  # 错误计数
        
        # WebSocket 指标
        self.ws_connections = 0
        self.ws_messages_sent = 0
        self.ws_messages_received = 0
        
        # 系统指标
        self.cpu_percent = 0.0
        self.memory_percent = 0.0
        self.memory_mb = 0.0
        
        # 启动时间
        self.start_time = datetime.now()
        
        # 监控任务
        self._monitor_task: Optional[asyncio.Task] = None
    
    async def start_monitoring(self, interval: float = 5.0) -> None:
        """启动系统监控"""
        async def monitor_loop():
            while True:
                try:
                    self._collect_system_metrics()
                    await asyncio.sleep(interval)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    self.logger.error(f"监控收集失败：{e}")
                    await asyncio.sleep(interval)
        
        self._monitor_task = asyncio.create_task(monitor_loop())
        self.logger.info("性能监控已启动")
    
    async def stop_monitoring(self) -> None:
        """停止系统监控"""
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        self.logger.info("性能监控已停止")
    
    def _collect_system_metrics(self) -> None:
        """收集系统指标"""
        self.cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.Process().memory_info()
        self.memory_mb = memory.rss / 1024 / 1024
        self.memory_percent = psutil.Process().memory_percent()
    
    def record_request(self, latency_ms: float, is_error: bool = False) -> None:
        """记录请求指标"""
        self.request_latencies.append({
            'timestamp': datetime.now(),
            'latency_ms': latency_ms
        })
        
        self.request_counts.append({
            'timestamp': datetime.now(),
            'count': 1
        })
        
        if is_error:
            self.error_counts.append({
                'timestamp': datetime.now(),
                'count': 1
            })
    
    def record_ws_message(self, direction: str) -> None:
        """记录 WebSocket 消息"""
        if direction == 'sent':
            self.ws_messages_sent += 1
        elif direction == 'received':
            self.ws_messages_received += 1
    
    def update_ws_connections(self, delta: int) -> None:
        """更新 WebSocket 连接数"""
        self.ws_connections += delta
    
    def get_metrics(self) -> Dict[str, Any]:
        """获取当前指标"""
        # 计算延迟统计
        latencies = [x['latency_ms'] for x in self.request_latencies]
        if latencies:
            avg_latency = sum(latencies) / len(latencies)
            p95_latency = sorted(latencies)[int(len(latencies) * 0.95)] if len(latencies) > 20 else avg_latency
            p99_latency = sorted(latencies)[int(len(latencies) * 0.99)] if len(latencies) > 100 else avg_latency
        else:
            avg_latency = p95_latency = p99_latency = 0.0
        
        # 计算请求率
        now = datetime.now()
        recent_requests = sum(
            1 for x in self.request_counts
            if (now - x['timestamp']).total_seconds() < 60
        )
        
        # 计算错误率
        recent_errors = sum(
            1 for x in self.error_counts
            if (now - x['timestamp']).total_seconds() < 60
        )
        error_rate = (recent_errors / recent_requests * 100) if recent_requests > 0 else 0.0
        
        return {
            'timestamp': now.isoformat(),
            'uptime_seconds': (now - self.start_time).total_seconds(),
            
            # 延迟指标
            'latency_avg_ms': round(avg_latency, 2),
            'latency_p95_ms': round(p95_latency, 2),
            'latency_p99_ms': round(p99_latency, 2),
            
            # 请求指标
            'requests_per_minute': recent_requests,
            'error_rate_percent': round(error_rate, 2),
            
            # WebSocket 指标
            'websocket_connections': self.ws_connections,
            'ws_messages_sent': self.ws_messages_sent,
            'ws_messages_received': self.ws_messages_received,
            
            # 系统指标
            'cpu_percent': self.cpu_percent,
            'memory_mb': round(self.memory_mb, 2),
            'memory_percent': self.memory_percent,
        }
    
    def print_metrics(self) -> None:
        """打印当前指标"""
        metrics = self.get_metrics()
        self.logger.info("=" * 60)
        self.logger.info("性能指标")
        self.logger.info("=" * 60)
        self.logger.info(f"运行时间：{metrics['uptime_seconds']:.0f} 秒")
        self.logger.info(f"请求延迟：avg={metrics['latency_avg_ms']:.2f}ms, p95={metrics['latency_p95_ms']:.2f}ms, p99={metrics['latency_p99_ms']:.2f}ms")
        self.logger.info(f"请求速率：{metrics['requests_per_minute']} 次/分钟")
        self.logger.info(f"错误率：{metrics['error_rate_percent']:.2f}%")
        self.logger.info(f"WebSocket 连接：{metrics['websocket_connections']}")
        self.logger.info(f"CPU 使用率：{metrics['cpu_percent']:.1f}%")
        self.logger.info(f"内存使用：{metrics['memory_mb']:.2f}MB ({metrics['memory_percent']:.1f}%)")
        self.logger.info("=" * 60)


# 全局指标收集器
metrics_collector = MetricsCollector()


def get_metrics_collector() -> MetricsCollector:
    """获取指标收集器实例"""
    return metrics_collector


class RequestTimer:
    """请求计时器 - 用于记录请求延迟"""
    
    def __init__(self, operation: str = "request"):
        self.operation = operation
        self.start_time: Optional[float] = None
        self.metrics = get_metrics_collector()
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            latency_ms = (time.time() - self.start_time) * 1000
            self.metrics.record_request(latency_ms, is_error=(exc_type is not None))
        return False


class AsyncRequestTimer:
    """异步请求计时器"""
    
    def __init__(self, operation: str = "request"):
        self.operation = operation
        self.start_time: Optional[float] = None
        self.metrics = get_metrics_collector()
    
    async def __aenter__(self):
        self.start_time = time.time()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            latency_ms = (time.time() - self.start_time) * 1000
            self.metrics.record_request(latency_ms, is_error=(exc_type is not None))
        return False
