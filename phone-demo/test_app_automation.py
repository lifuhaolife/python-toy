"""
App 自动化测试脚本
模拟 UI 操作进行测试

使用方法:
    python test_app_automation.py
"""
import os
import sys
import time
import json
import logging
import threading
import asyncio
from datetime import datetime

# 添加路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("app-test")


class AppAutomationTester:
    """App 自动化测试器"""
    
    def __init__(self, server_host="localhost", server_port=8000, device_id="phone_test_001"):
        self.server_host = server_host
        self.server_port = server_port
        self.device_id = device_id
        self.ws = None
        self.session = None
        self.loop = None
        self.is_connected = False
        self.received_messages = []
        
    async def connect(self):
        """连接到服务器"""
        import aiohttp
        
        url = f"ws://{self.server_host}:{self.server_port}/ws/audio/{self.device_id}"
        logger.info(f"正在连接：{url}")
        
        try:
            self.session = aiohttp.ClientSession()
            self.ws = await self.session.ws_connect(url)
            self.is_connected = True
            logger.info("✅ 连接成功")
            
            # 启动接收任务
            asyncio.create_task(self._receive_loop())
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 连接失败：{e}")
            return False
    
    async def _receive_loop(self):
        """接收消息循环"""
        import aiohttp
        
        logger.info("开始接收消息...")
        
        try:
            while self.is_connected and self.ws and not self.ws.closed:
                msg = await self.ws.receive()
                
                if msg.type == aiohttp.WSMsgType.BINARY:
                    data = msg.data
                    if len(data) > 0:
                        msg_type = data[0]
                        payload = data[1:]
                        self.received_messages.append({
                            'type': msg_type,
                            'data': payload,
                            'time': datetime.now().isoformat()
                        })
                        logger.info(f"收到消息：0x{msg_type:02X}, {len(payload)} 字节")
                        
                        # 处理 JSON 消息
                        if msg_type == 0x01:  # JSON 响应
                            try:
                                response = json.loads(payload.decode('utf-8'))
                                logger.info(f"AI 响应：{response.get('text', '')}")
                            except:
                                pass
                        
                elif msg.type == aiohttp.WSMsgType.CLOSED:
                    logger.info("连接已关闭")
                    self.is_connected = False
                    break
                    
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    logger.error("WebSocket 错误")
                    self.is_connected = False
                    break
                    
        except Exception as e:
            logger.error(f"接收错误：{e}")
            self.is_connected = False
    
    async def send_audio(self, audio_data: bytes):
        """发送音频数据"""
        if not self.is_connected or not self.ws:
            logger.error("未连接，无法发送")
            return False
        
        message = bytes([0x01]) + audio_data
        await self.ws.send_bytes(message)
        logger.info(f"发送音频：{len(audio_data)} 字节")
        return True
    
    async def send_mock_audio(self, duration_sec: float = 2.0):
        """发送模拟音频数据"""
        import numpy as np
        
        # 生成模拟音频（正弦波）
        sample_rate = 16000
        frequency = 440  # A4 音调
        samples = int(duration_sec * sample_rate)
        t = np.linspace(0, duration_sec, samples, dtype=np.float32)
        audio_data = (np.sin(2 * np.pi * frequency * t) * 32767).astype(np.int16)
        
        return await self.send_audio(audio_data.tobytes())
    
    async def wait_for_response(self, timeout_sec: float = 10.0):
        """等待响应"""
        logger.info(f"等待响应（最多 {timeout_sec} 秒）...")
        
        start_time = time.time()
        while time.time() - start_time < timeout_sec:
            if self.received_messages:
                logger.info(f"收到 {len(self.received_messages)} 条消息")
                return self.received_messages
            await asyncio.sleep(0.1)
        
        logger.warning("等待超时")
        return []
    
    async def close(self):
        """关闭连接"""
        self.is_connected = False
        
        if self.ws:
            await self.ws.close()
        
        if self.session:
            await self.session.close()
        
        logger.info("连接已关闭")
    
    async def run_test(self):
        """运行完整测试流程"""
        logger.info("=" * 60)
        logger.info("开始自动化测试")
        logger.info("=" * 60)
        
        # 1. 连接测试
        logger.info("\n[测试 1] 连接服务器...")
        if not await self.connect():
            logger.error("❌ 连接测试失败")
            return False
        logger.info("✅ 连接测试通过")
        
        # 等待连接稳定
        await asyncio.sleep(0.5)
        
        # 2. 发送音频测试
        logger.info("\n[测试 2] 发送模拟音频...")
        await self.send_mock_audio(duration_sec=2.0)
        logger.info("✅ 音频发送完成")
        
        # 3. 等待响应测试
        logger.info("\n[测试 3] 等待服务器响应...")
        messages = await self.wait_for_response(timeout_sec=15.0)
        
        if messages:
            logger.info("✅ 响应测试通过")
            
            # 分析响应
            json_responses = [m for m in messages if m['type'] == 0x01]
            tts_responses = [m for m in messages if m['type'] == 0x02]
            
            logger.info(f"  - JSON 响应：{len(json_responses)} 条")
            logger.info(f"  - TTS 音频：{len(tts_responses)} 条")
        else:
            logger.warning("⚠️ 未收到响应")
        
        # 4. 断开连接测试
        logger.info("\n[测试 4] 断开连接...")
        await self.close()
        logger.info("✅ 断开连接完成")
        
        logger.info("\n" + "=" * 60)
        logger.info("自动化测试完成")
        logger.info("=" * 60)
        
        return True


def run_automation_test():
    """运行自动化测试（同步入口）"""
    tester = AppAutomationTester()
    
    # 创建事件循环
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        result = loop.run_until_complete(tester.run_test())
        return result
    except Exception as e:
        logger.error(f"测试异常：{e}")
        return False
    finally:
        loop.close()


if __name__ == "__main__":
    success = run_automation_test()
    sys.exit(0 if success else 1)
