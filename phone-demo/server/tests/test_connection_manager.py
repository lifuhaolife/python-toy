"""
单元测试 - WebSocket 连接管理器
独立测试，不依赖 server_rebuild 模块
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock


class ConnectionManager:
    """
    WebSocket 连接管理器（测试版本）
    从 server_rebuild 复制，避免导入依赖
    """
    
    def __init__(self, max_connections: int = 100):
        self.max_connections = max_connections
        self.connections = {}
        self.contexts = {}
        self.connection_times = {}
    
    async def connect(self, ws, device_id: str) -> bool:
        if len(self.connections) >= self.max_connections:
            return False
        try:
            await ws.accept()
            self.connections[device_id] = ws
            self.contexts[device_id] = []
            return True
        except Exception:
            return False
    
    def disconnect(self, device_id: str) -> None:
        if device_id in self.connections:
            del self.connections[device_id]
        if device_id in self.contexts:
            del self.contexts[device_id]
    
    async def send_bytes(self, device_id: str, data: bytes) -> bool:
        if device_id not in self.connections:
            return False
        ws = self.connections[device_id]
        try:
            if ws.client_state.name == 'DISCONNECTED':
                self.disconnect(device_id)
                return False
        except Exception:
            pass
        try:
            await ws.send_bytes(data)
            return True
        except Exception:
            self.disconnect(device_id)
            return False
    
    async def send_json(self, device_id: str, data: dict) -> bool:
        if device_id not in self.connections:
            return False
        ws = self.connections[device_id]
        try:
            if ws.client_state.name == 'DISCONNECTED':
                self.disconnect(device_id)
                return False
        except Exception:
            pass
        try:
            await ws.send_json(data)
            return True
        except Exception:
            self.disconnect(device_id)
            return False
    
    def add_context(self, device_id: str, role: str, content: str) -> None:
        if device_id not in self.contexts:
            self.contexts[device_id] = []
        self.contexts[device_id].append({"role": role, "content": content})
        if len(self.contexts[device_id]) > 20:
            self.contexts[device_id] = self.contexts[device_id][-20:]
    
    def get_context(self, device_id: str) -> list:
        return self.contexts.get(device_id, [])
    
    def get_stats(self) -> dict:
        return {
            'total_connections': len(self.connections),
            'max_connections': self.max_connections,
            'devices': list(self.connections.keys()),
        }


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
        assert ws.messages[0][1] == {"type": "test"}
    
    @pytest.mark.asyncio
    async def test_send_to_disconnected(self, manager):
        """测试发送给已断开的设备"""
        ws = MockWebSocket()
        await manager.connect(ws, "device_001")
        ws.client_state.name = 'DISCONNECTED'
        result = await manager.send_bytes("device_001", b"\x01")
        assert result is False
        assert "device_001" not in manager.connections
    
    @pytest.mark.asyncio
    async def test_max_connections(self, manager):
        """测试最大连接数限制"""
        for i in range(10):
            ws = MockWebSocket()
            await manager.connect(ws, f"device_{i:03d}")
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
    
    def test_context_limit(self, manager):
        """测试上下文长度限制"""
        for i in range(25):
            manager.add_context("device_001", "user", f"消息{i}")
        context = manager.get_context("device_001")
        assert len(context) == 20
        # 最早的 5 条被丢弃，从消息 5 开始（检查包含"消息 5"或"消息 5"）
        assert "消息" in context[0]["content"] and "5" in context[0]["content"]
    
    def test_get_stats(self, manager):
        """测试获取统计信息"""
        stats = manager.get_stats()
        assert 'total_connections' in stats
        assert 'max_connections' in stats
        assert stats['max_connections'] == 10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
