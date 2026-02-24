"""
单元测试 - WebSocket 连接管理器
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock

import sys
import os

# 添加路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'server'))

from server_rebuild import ConnectionManager


class MockWebSocket:
    """模拟 WebSocket"""
    
    def __init__(self):
        self.client_state = MagicMock()
        self.client_state.name = 'CONNECTED'
        self.messages = []
    
    async def accept(self):
        pass
    
    async def send_bytes(self, data):
        self.messages.append(('bytes', data))
    
    async def send_json(self, data):
        self.messages.append(('json', data))
    
    async def close(self, code=1000, reason=""):
        self.client_state.name = 'DISCONNECTED'


class TestConnectionManager:
    """连接管理器测试"""
    
    @pytest.fixture
    def manager(self):
        return ConnectionManager(max_connections=10)
    
    @pytest.mark.asyncio
    async def test_connect(self, manager):
        """测试连接"""
        ws = MockWebSocket()
        result = await manager.connect(ws, "device_001")
        
        assert result is True
        assert "device_001" in manager.connections
        assert len(manager.connections) == 1
    
    @pytest.mark.asyncio
    async def test_disconnect(self, manager):
        """测试断开连接"""
        ws = MockWebSocket()
        await manager.connect(ws, "device_001")
        
        manager.disconnect("device_001")
        
        assert "device_001" not in manager.connections
    
    @pytest.mark.asyncio
    async def test_send_bytes(self, manager):
        """测试发送二进制数据"""
        ws = MockWebSocket()
        await manager.connect(ws, "device_001")
        
        result = await manager.send_bytes("device_001", b"\x01\x02\x03")
        
        assert result is True
        assert len(ws.messages) == 1
        assert ws.messages[0][0] == 'bytes'
    
    @pytest.mark.asyncio
    async def test_send_json(self, manager):
        """测试发送 JSON 数据"""
        ws = MockWebSocket()
        await manager.connect(ws, "device_001")
        
        result = await manager.send_json("device_001", {"type": "test"})
        
        assert result is True
        assert len(ws.messages) == 1
        assert ws.messages[0][0] == 'json'
        assert ws.messages[0][1] == {"type": "test"}
    
    @pytest.mark.asyncio
    async def test_send_to_disconnected(self, manager):
        """测试发送给已断开的设备"""
        ws = MockWebSocket()
        await manager.connect(ws, "device_001")
        
        # 模拟断开
        ws.client_state.name = 'DISCONNECTED'
        
        result = await manager.send_bytes("device_001", b"\x01")
        
        assert result is False
        assert "device_001" not in manager.connections
    
    @pytest.mark.asyncio
    async def test_max_connections(self, manager):
        """测试最大连接数限制"""
        # 创建 10 个连接（达到上限）
        for i in range(10):
            ws = MockWebSocket()
            await manager.connect(ws, f"device_{i:03d}")
        
        # 第 11 个连接应该失败
        ws = MockWebSocket()
        result = await manager.connect(ws, "device_overflow")
        
        assert result is False
    
    def test_add_context(self, manager):
        """测试添加上下文"""
        manager.add_context("device_001", "user", "你好")
        manager.add_context("device_001", "assistant", "你好！")
        
        context = manager.get_context("device_001")
        
        assert len(context) == 2
        assert context[0]["role"] == "user"
        assert context[0]["content"] == "你好"
    
    def test_context_limit(self, manager):
        """测试上下文长度限制"""
        # 添加 25 条消息（超过 20 条限制）
        for i in range(25):
            manager.add_context("device_001", "user", f"消息{i}")
        
        context = manager.get_context("device_001")
        
        assert len(context) == 20
        assert context[0]["content"] == "消息 5"  # 最早的 5 条被丢弃
    
    def test_get_stats(self, manager):
        """测试获取统计信息"""
        stats = manager.get_stats()
        
        assert 'total_connections' in stats
        assert 'max_connections' in stats
        assert stats['max_connections'] == 10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
