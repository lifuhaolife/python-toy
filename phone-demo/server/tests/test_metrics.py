"""
单元测试 - 性能监控
"""
import pytest
import asyncio
import time

from metrics import MetricsCollector, RequestTimer, AsyncRequestTimer


class TestMetricsCollector:
    """指标收集器测试"""
    
    @pytest.fixture
    def collector(self):
        return MetricsCollector(max_samples=100)
    
    def test_record_request(self, collector):
        """测试记录请求"""
        collector.record_request(100.0, is_error=False)
        collector.record_request(200.0, is_error=True)
        
        assert len(collector.request_latencies) == 2
        assert len(collector.error_counts) == 1
    
    def test_get_metrics(self, collector):
        """测试获取指标"""
        # 记录一些请求
        for i in range(10):
            collector.record_request(float(i * 10), is_error=(i == 5))
        
        metrics = collector.get_metrics()
        
        assert 'latency_avg_ms' in metrics
        assert 'requests_per_minute' in metrics
        assert 'error_rate_percent' in metrics
        assert metrics['websocket_connections'] == 0
    
    def test_ws_message_count(self, collector):
        """测试 WebSocket 消息计数"""
        collector.record_ws_message('sent')
        collector.record_ws_message('sent')
        collector.record_ws_message('received')
        
        assert collector.ws_messages_sent == 2
        assert collector.ws_messages_received == 1
    
    def test_update_ws_connections(self, collector):
        """测试更新 WebSocket 连接数"""
        collector.update_ws_connections(1)
        collector.update_ws_connections(1)
        collector.update_ws_connections(-1)
        
        assert collector.ws_connections == 1


class TestRequestTimer:
    """请求计时器测试"""
    
    def test_request_timer(self):
        """测试请求计时器"""
        collector = MetricsCollector(max_samples=100)
        # 使用独立的 collector 实例
        import metrics
        original_get = metrics.get_metrics_collector
        metrics.get_metrics_collector = lambda: collector
        
        try:
            with RequestTimer("test_operation"):
                time.sleep(0.01)  # 10ms
            
            assert len(collector.request_latencies) >= 1
            assert collector.request_latencies[0]['latency_ms'] >= 10
        finally:
            metrics.get_metrics_collector = original_get
    
    def test_request_timer_error(self):
        """测试请求计时器错误情况"""
        collector = MetricsCollector(max_samples=100)
        import metrics
        original_get = metrics.get_metrics_collector
        metrics.get_metrics_collector = lambda: collector
        
        try:
            try:
                with RequestTimer("test_operation"):
                    time.sleep(0.01)
                    raise ValueError("Test error")
            except ValueError:
                pass
            
            assert len(collector.request_latencies) >= 1
            assert len(collector.error_counts) >= 1
        finally:
            metrics.get_metrics_collector = original_get


@pytest.mark.asyncio
class TestAsyncRequestTimer:
    """异步请求计时器测试"""
    
    async def test_async_request_timer(self):
        """测试异步请求计时器"""
        collector = MetricsCollector(max_samples=100)
        import metrics
        original_get = metrics.get_metrics_collector
        metrics.get_metrics_collector = lambda: collector
        
        try:
            async with AsyncRequestTimer("test_operation"):
                await asyncio.sleep(0.01)
            
            assert len(collector.request_latencies) >= 1
        finally:
            metrics.get_metrics_collector = original_get
    
    async def test_async_request_timer_error(self):
        """测试异步请求计时器错误情况"""
        collector = MetricsCollector(max_samples=100)
        import metrics
        original_get = metrics.get_metrics_collector
        metrics.get_metrics_collector = lambda: collector
        
        try:
            try:
                async with AsyncRequestTimer("test_operation"):
                    await asyncio.sleep(0.01)
                    raise ValueError("Test error")
            except ValueError:
                pass
            
            assert len(collector.request_latencies) >= 1
            assert len(collector.error_counts) >= 1
        finally:
            metrics.get_metrics_collector = original_get


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
