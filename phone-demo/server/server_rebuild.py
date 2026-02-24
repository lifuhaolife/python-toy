"""
儿童智能语音玩具 - 服务器端（重构版）
支持手机 APP 和 ESP32 设备连接

主要改进:
1. 使用新的配置和日志系统
2. 优化的 WebSocket 连接管理
3. 数据库连接池支持
4. 性能监控和指标收集
5. 完善的错误处理和重试机制

作者：Toy Project
版本：3.0.0-rebuild
"""
import os
import sys
import json
import asyncio
import logging
from datetime import datetime
from contextlib import asynccontextmanager
from typing import Dict, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

# 导入新模块
from config import get_config, Config
from logger import setup_logger, PerformanceLogger
from db_pool import get_database_pool, DatabasePool
from database import Database
from memory_manager import MemoryManager, get_memory_manager
from metrics import get_metrics_collector, AsyncRequestTimer

# 修复 Windows 控制台编码问题
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')


class ConnectionManager:
    """
    WebSocket 连接管理器（重构版）
    
    改进:
    1. 连接状态追踪
    2. 发送前状态检查
    3. 自动清理断开连接
    4. 并发控制
    """
    
    def __init__(self, max_connections: int = 100):
        self.max_connections = max_connections
        self.connections: Dict[str, WebSocket] = {}
        self.contexts: Dict[str, list] = {}
        self.connection_times: Dict[str, datetime] = {}
        self.logger = logging.getLogger("connection_manager")
        
        # 信号量控制并发
        self._semaphore: Optional[asyncio.Semaphore] = None
    
    def _get_semaphore(self) -> asyncio.Semaphore:
        """获取信号量（懒加载）"""
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self.max_connections)
        return self._semaphore
    
    async def connect(self, ws: WebSocket, device_id: str) -> bool:
        """
        接受新连接
        
        Returns:
            bool: 连接是否成功
        """
        # 检查连接数限制
        if len(self.connections) >= self.max_connections:
            self.logger.warning(f"达到最大连接数限制：{self.max_connections}")
            await ws.close(code=1013, reason="Too many connections")
            return False
        
        try:
            await ws.accept()
            self.connections[device_id] = ws
            self.contexts[device_id] = []
            self.connection_times[device_id] = datetime.now()
            
            # 更新指标
            metrics = get_metrics_collector()
            metrics.update_ws_connections(1)
            
            self.logger.info(f"[WebSocket] 新连接：{device_id} (当前连接数：{len(self.connections)})")
            return True
            
        except Exception as e:
            self.logger.error(f"接受连接失败：{e}")
            try:
                await ws.close()
            except:
                pass
            return False
    
    def disconnect(self, device_id: str) -> None:
        """断开连接"""
        if device_id in self.connections:
            del self.connections[device_id]
        if device_id in self.contexts:
            del self.contexts[device_id]
        if device_id in self.connection_times:
            del self.connection_times[device_id]
        
        # 更新指标
        metrics = get_metrics_collector()
        metrics.update_ws_connections(-1)
        
        self.logger.info(f"[WebSocket] 连接断开：{device_id} (当前连接数：{len(self.connections)})")
    
    async def send_bytes(self, device_id: str, data: bytes) -> bool:
        """
        发送二进制数据（带连接状态检查）
        
        Returns:
            bool: 发送是否成功
        """
        if device_id not in self.connections:
            self.logger.debug(f"发送失败：设备 {device_id} 未连接")
            return False
        
        ws = self.connections[device_id]
        
        # 检查连接状态
        try:
            if ws.client_state.name == 'DISCONNECTED':
                self.logger.warning(f"发送失败：设备 {device_id} 已断开")
                self.disconnect(device_id)
                return False
        except Exception:
            pass  # 如果无法获取状态，尝试发送
        
        try:
            await ws.send_bytes(data)
            
            # 更新指标
            metrics = get_metrics_collector()
            metrics.record_ws_message('sent')
            
            return True
            
        except Exception as e:
            self.logger.error(f"发送数据失败：{e}")
            self.disconnect(device_id)
            return False
    
    async def send_json(self, device_id: str, data: dict) -> bool:
        """
        发送 JSON 数据（带连接状态检查）
        
        Returns:
            bool: 发送是否成功
        """
        if device_id not in self.connections:
            self.logger.debug(f"发送 JSON 失败：设备 {device_id} 未连接")
            return False
        
        ws = self.connections[device_id]
        
        # 检查连接状态
        try:
            if ws.client_state.name == 'DISCONNECTED':
                self.logger.warning(f"发送 JSON 失败：设备 {device_id} 已断开")
                self.disconnect(device_id)
                return False
        except Exception:
            pass
        
        try:
            await ws.send_json(data)
            
            # 更新指标
            metrics = get_metrics_collector()
            metrics.record_ws_message('sent')
            
            return True
            
        except Exception as e:
            self.logger.error(f"发送 JSON 失败：{e}")
            self.disconnect(device_id)
            return False
    
    def add_context(self, device_id: str, role: str, content: str) -> None:
        """添加对话上下文"""
        if device_id not in self.contexts:
            self.contexts[device_id] = []
        
        self.contexts[device_id].append({"role": role, "content": content})
        
        # 限制上下文长度
        if len(self.contexts[device_id]) > 20:
            self.contexts[device_id] = self.contexts[device_id][-20:]
    
    def get_context(self, device_id: str) -> list:
        """获取对话上下文"""
        return self.contexts.get(device_id, [])
    
    def get_connection_duration(self, device_id: str) -> float:
        """获取连接时长（秒）"""
        if device_id not in self.connection_times:
            return 0.0
        return (datetime.now() - self.connection_times[device_id]).total_seconds()
    
    def get_stats(self) -> dict:
        """获取连接统计信息"""
        return {
            'total_connections': len(self.connections),
            'max_connections': self.max_connections,
            'devices': list(self.connections.keys()),
        }


class SimpleAIClient:
    """
    AI 客户端（重构版）
    
    改进:
    1. 连接池支持
    2. 重试机制
    3. 完整的错误处理
    4. 性能监控
    """
    
    def __init__(self, api_key: str, db=None):
        self.api_key = api_key
        self.client = httpx.AsyncClient(
            timeout=60.0,
            limits=httpx.Limits(
                max_keepalive_connections=10,
                max_connections=20
            )
        )
        self.db = db
        self.logger = logging.getLogger("ai_client")
        
        self.system_prompt = """你是一个亲切友好的 AI 大姐姐，专门陪伴 3-12 岁的儿童。
你的特点是：
1. 语气温柔亲切，使用简单易懂的语言
2. 内容积极向上，传递正能量
3. 善于引导孩子学习和思考
4. 避免复杂词汇，多用比喻和故事
5. 注意安全问题，不涉及危险话题
6. 每次回复控制在 50 字以内，适合语音播放

请始终保持耐心和鼓励的态度，让孩子感受到关爱。"""
    
    async def chat_stream(self, message: str, context: list = None, 
                         device_id: str = None, session_id: str = None):
        """
        发送对话请求（流式响应）
        
        Yields:
            生成的文本片段
        """
        import uuid
        from config import get_config
        
        config = get_config()
        request_id = str(uuid.uuid4())
        request_start_time = datetime.now()
        
        messages = [
            {"role": "system", "content": self.system_prompt},
        ]
        
        if context:
            messages.extend(context[-5:])
        
        messages.append({"role": "user", "content": message})
        
        request_data = {
            "model": config.AI_MODEL,
            "messages": messages,
            "max_tokens": config.AI_MAX_TOKENS,
            "temperature": config.AI_TEMPERATURE,
            "stream": True
        }
        
        api_endpoint = f"{config.AI_API_BASE_URL}/chat/completions"
        
        full_content = ""
        stream_chunks = 0
        response_status = None
        usage = {}
        finish_reason = None
        
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            # 使用异步流式请求
            async with self.client.stream(
                "POST",
                api_endpoint,
                headers=headers,
                json=request_data
            ) as response:
                response_status = response.status_code
                
                async for line in response.aiter_lines():
                    if line.startswith("data:"):
                        data_str = line[5:].strip()
                        if data_str == "[DONE]":
                            break
                        
                        try:
                            data_json = json.loads(data_str)
                            if "choices" in data_json and len(data_json["choices"]) > 0:
                                delta = data_json["choices"][0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    full_content += content
                                    stream_chunks += 1
                                    yield content
                                
                                if "finish_reason" in data_json["choices"][0]:
                                    finish_reason = data_json["choices"][0]["finish_reason"]
                                
                                if "usage" in data_json:
                                    usage = data_json["usage"]
                        
                        except json.JSONDecodeError:
                            continue
            
            # 记录成功响应
            await self._log_success(
                request_id=request_id,
                device_id=device_id,
                session_id=session_id,
                request_start_time=request_start_time,
                request_data=request_data,
                response_status=response_status,
                full_content=full_content,
                usage=usage,
                finish_reason=finish_reason,
                stream_chunks=stream_chunks,
                context=context
            )
            
        except Exception as e:
            # 记录失败响应
            await self._log_error(
                request_id=request_id,
                device_id=device_id,
                session_id=session_id,
                request_start_time=request_start_time,
                request_data=request_data,
                error=e,
                context=context
            )
            
            yield f"抱歉，我现在有点累。(错误：{str(e)[:30]})"
    
    async def _log_success(self, **kwargs):
        """记录成功的 AI 请求"""
        if not self.db:
            return
        
        request_end_time = datetime.now()
        duration_ms = int((request_end_time - kwargs['request_start_time']).total_seconds() * 1000)
        
        try:
            # 保存到对话记录
            conversation_id = await self.db.save_conversation(
                device_id=kwargs.get('device_id'),
                session_id=kwargs.get('session_id'),
                user_message=kwargs['request_data']['messages'][-1]['content'],
                ai_message=kwargs['full_content'],
                duration_ms=duration_ms,
                total_tokens=kwargs['usage'].get('total_tokens', 0),
                context_messages=kwargs['request_data']['messages'],
                request_data=kwargs['request_data'],
                response_data={"choices": [{"message": {"content": kwargs['full_content']}}], "usage": kwargs['usage']},
                model_name=kwargs['request_data']['model'],
                temperature=kwargs['request_data']['temperature'],
                max_tokens=kwargs['request_data']['max_tokens'],
                finish_reason=kwargs['finish_reason'] or 'stop',
                prompt_tokens=kwargs['usage'].get('prompt_tokens', 0),
                completion_tokens=kwargs['usage'].get('completion_tokens', 0),
                is_stream=True
            )
            
            # 记录 API 日志
            await self.db.log_ai_request(
                request_id=kwargs['request_id'],
                device_id=kwargs.get('device_id'),
                session_id=kwargs.get('session_id'),
                conversation_id=conversation_id,
                request_body=kwargs['request_data'],
                response_body={"content": kwargs['full_content'], "usage": kwargs['usage']},
                response_status=kwargs['response_status'],
                duration_ms=duration_ms,
                is_success=True,
                model=kwargs['request_data']['model'],
                is_stream=True,
                stream_chunks_count=kwargs['stream_chunks'],
                request_start_time=kwargs['request_start_time'],
                request_end_time=request_end_time
            )
            
        except Exception as e:
            self.logger.error(f"记录 AI 请求日志失败：{e}")
    
    async def _log_error(self, **kwargs):
        """记录失败的 AI 请求"""
        if not self.db:
            return
        
        request_end_time = datetime.now()
        duration_ms = int((request_end_time - kwargs['request_start_time']).total_seconds() * 1000)
        
        try:
            await self.db.log_ai_request(
                request_id=kwargs['request_id'],
                device_id=kwargs.get('device_id'),
                session_id=kwargs.get('session_id'),
                request_body=kwargs['request_data'],
                response_status=getattr(kwargs['error'], 'response', None).status_code if hasattr(kwargs['error'], 'response') else 0,
                duration_ms=duration_ms,
                is_success=False,
                error_message=str(kwargs['error']),
                error_type=type(kwargs['error']).__name__,
                model=kwargs['request_data']['model'],
                is_stream=True,
                request_start_time=kwargs['request_start_time'],
                request_end_time=request_end_time
            )
        except Exception as e:
            self.logger.error(f"记录 AI 错误日志失败：{e}")
    
    async def close(self):
        """关闭客户端"""
        await self.client.aclose()


class SimpleTTSClient:
    """TTS 客户端（重构版）"""
    
    def __init__(self):
        self.logger = logging.getLogger("tts_client")
    
    async def synthesize(self, text: str) -> bytes:
        """合成语音"""
        try:
            import edge_tts
            import tempfile
            
            output_file = tempfile.mktemp(suffix=".mp3")
            
            communicate = edge_tts.Communicate(
                text,
                "zh-CN-XiaoxiaoNeural",
                rate="+0%",
                volume="+0%",
                pitch="+0Hz"
            )
            
            await communicate.save(output_file)
            
            with open(output_file, "rb") as f:
                audio_data = f.read()
            
            os.remove(output_file)
            return audio_data
            
        except Exception as e:
            self.logger.error(f"TTS 合成失败：{e}")
            return b''


class SimpleASRClient:
    """ASR 客户端（重构版）"""
    
    def __init__(self):
        self.model = None
        self.logger = logging.getLogger("asr_client")
        self.model_path = os.path.join(os.path.dirname(__file__), 'models', 'whisper-tiny')
        
        self._load_model()
    
    def _load_model(self):
        """加载本地 Whisper 模型"""
        try:
            from faster_whisper import WhisperModel
            
            if not os.path.exists(self.model_path):
                self.logger.error(f"模型不存在：{self.model_path}")
                return
            
            self.model = WhisperModel(
                self.model_path,
                device="cpu",
                compute_type="int8"
            )
            self.logger.info("Whisper 模型加载成功")
            
        except Exception as e:
            self.logger.error(f"模型加载失败：{e}")
            self.model = None
    
    def transcribe(self, audio_data: bytes) -> str:
        """语音识别"""
        if self.model is None:
            self.logger.error("模型未加载")
            return ""
        
        try:
            import numpy as np
            audio_array = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
            
            segments, info = self.model.transcribe(
                audio_array,
                language="zh",
                vad_filter=True,
                vad_parameters=dict(
                    threshold=0.5,
                    min_silence_duration_ms=500
                )
            )
            
            text = ""
            for segment in segments:
                text += segment.text
            
            text = text.strip()
            
            if text:
                self.logger.info(f"[ASR] 识别结果：{text}")
            else:
                self.logger.warning("[ASR] 未识别到有效语音")
            
            return text
            
        except Exception as e:
            self.logger.error(f"语音识别失败：{e}")
            return ""


# 全局对象
manager = ConnectionManager(max_connections=100)
ai_client = None
tts_client = None
asr_client = None
db: Database = None
memory_mgr: MemoryManager = None
metrics = None
logger = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global ai_client, tts_client, asr_client, db, memory_mgr, metrics, logger
    
    # 初始化配置
    config = get_config()
    config.print_config()
    
    # 初始化日志
    logger = setup_logger(
        name="toy-server",
        log_dir=config.LOG_DIR,
        level=config.LOG_LEVEL,
        max_bytes=config.LOG_MAX_BYTES,
        backup_count=config.LOG_BACKUP_COUNT
    )
    
    logger.info("=" * 80)
    logger.info("儿童智能语音玩具服务器 v3.0.0-rebuild")
    logger.info("=" * 80)
    
    # 初始化数据库连接池
    logger.info("初始化数据库连接池...")
    db_pool = get_database_pool()
    await db_pool.connect()
    
    # 初始化数据库操作
    logger.info("初始化数据库操作...")
    db = get_database()
    await db.connect()
    
    # 初始化 AI 客户端
    logger.info("初始化 AI 客户端...")
    ai_client = SimpleAIClient(config.AI_API_KEY, db=db)
    
    # 初始化 TTS 客户端
    logger.info("初始化 TTS 客户端...")
    tts_client = SimpleTTSClient()
    
    # 初始化 ASR 客户端
    logger.info("初始化 ASR 客户端...")
    asr_client = SimpleASRClient()
    
    # 初始化记忆管理器
    logger.info("初始化记忆管理器...")
    memory_mgr = get_memory_manager(db)
    
    # 初始化性能监控
    logger.info("初始化性能监控...")
    metrics = get_metrics_collector()
    await metrics.start_monitoring(interval=30.0)
    
    logger.info("=" * 80)
    logger.info(f"服务器地址：{config.HOST}:{config.PORT}")
    logger.info(f"最大连接数：{manager.max_connections}")
    logger.info(f"最大并发请求：{config.MAX_CONCURRENT_REQUESTS}")
    logger.info("=" * 80)
    
    yield
    
    # 清理资源
    logger.info("关闭服务器...")
    
    if metrics:
        await metrics.stop_monitoring()
    
    if ai_client:
        await ai_client.close()
    
    if db:
        await db.close()
    
    if db_pool:
        await db_pool.close()
    
    logger.info("服务器已关闭")


app = FastAPI(title="Toy Server", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {
        "service": "toy-server",
        "version": "3.0.0-rebuild",
        "status": "running"
    }


@app.get("/health")
async def health():
    """健康检查端点"""
    stats = manager.get_stats()
    db_stats = get_database_pool().get_pool_stats()
    
    return {
        "status": "healthy",
        "connections": stats['total_connections'],
        "max_connections": stats['max_connections'],
        "database": db_stats,
        "timestamp": datetime.now().isoformat()
    }


@app.get("/metrics")
async def get_metrics():
    """性能指标端点"""
    return get_metrics_collector().get_metrics()


@app.websocket("/ws/audio/{device_id}")
async def websocket_audio(ws: WebSocket, device_id: str):
    """WebSocket 音频接口"""
    global db, memory_mgr, ai_client, tts_client, asr_client, manager, logger, metrics
    
    if logger is None:
        logger = logging.getLogger("toy-server")
    
    logger.info("=" * 80)
    logger.info(f"[WebSocket] 新连接请求：{device_id}")
    logger.info("=" * 80)
    
    # 连接
    if not await manager.connect(ws, device_id):
        return
    
    # 注册设备
    if db:
        await db.register_device(device_id, device_type="phone")
        await db.update_device_status(device_id, last_seen=datetime.now())
    
    audio_buffer = bytearray()
    message_count = 0
    request_count = 0
    session_id = f"{device_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    # 音频阈值
    min_audio_duration = 1.0
    min_audio_bytes = int(16000 * min_audio_duration * 2)
    
    try:
        while True:
            data = await ws.receive_bytes()
            message_count += 1
            
            if len(data) == 0:
                continue
            
            msg_type = data[0]
            payload = data[1:]
            
            logger.debug(f"[消息 #{message_count}] 来自 {device_id}: 0x{msg_type:02X}, {len(payload)} 字节")
            
            # 更新指标
            if metrics:
                metrics.record_ws_message('received')
            
            if msg_type == 0x01:  # 音频数据
                audio_buffer.extend(payload)
                
                if len(audio_buffer) >= min_audio_bytes:
                    request_count += 1
                    
                    # 使用异步计时器
                    async with AsyncRequestTimer(f"request_{request_count}") as timer:
                        start_time = datetime.now()
                        logger.info(f"[处理] 请求 #{request_count} ({len(audio_buffer)/16000:.2f}秒音频)")
                        
                        # 1. 语音识别
                        user_text = asr_client.transcribe(bytes(audio_buffer))
                        
                        # 记录 ASR 日志
                        if db:
                            await db.log_asr(
                                device_id=device_id,
                                audio_duration_ms=int(len(audio_buffer)/16000*1000),
                                recognized_text=user_text,
                                success=bool(user_text)
                            )
                        
                        if not user_text:
                            logger.warning("[ASR] 未识别到有效语音，跳过")
                            audio_buffer.clear()
                            continue
                        
                        logger.info(f"[ASR] 识别结果：{user_text}")
                        
                        # 2. 构建上下文
                        if memory_mgr:
                            context = await memory_mgr.build_context(device_id)
                        else:
                            context = manager.get_context(device_id)
                        
                        # 3. AI 对话（流式）
                        logger.info("[AI] 开始流式对话...")
                        ai_response = ""
                        
                        await manager.send_json(device_id, {
                            "type": "stream_start",
                            "message_id": request_count
                        })
                        
                        async for chunk in ai_client.chat_stream(
                            user_text, context,
                            device_id=device_id,
                            session_id=session_id
                        ):
                            ai_response += chunk
                            await manager.send_json(device_id, {
                                "type": "stream_chunk",
                                "content": chunk
                            })
                        
                        await manager.send_json(device_id, {
                            "type": "stream_end",
                            "message_id": request_count,
                            "full_text": ai_response
                        })
                        
                        logger.info(f"[AI] 响应：{ai_response}")
                        
                        # 更新上下文和记忆
                        manager.add_context(device_id, "user", user_text)
                        manager.add_context(device_id, "assistant", ai_response)
                        
                        if memory_mgr:
                            await memory_mgr.save_conversation(
                                device_id=device_id,
                                session_id=session_id,
                                user_message=user_text,
                                ai_message=ai_response,
                                duration_ms=int((datetime.now() - start_time).total_seconds() * 1000)
                            )
                        
                        # 4. 发送完整响应
                        await manager.send_json(device_id, {
                            "type": "response",
                            "text": ai_response
                        })
                        
                        # 5. TTS 合成
                        tts_audio = await tts_client.synthesize(ai_response)
                        
                        if tts_audio:
                            logger.info(f"[TTS] 合成：{len(tts_audio)} 字节")
                            await manager.send_bytes(device_id, bytes([0x02]) + tts_audio)
                            
                            if db:
                                await db.log_tts(
                                    device_id=device_id,
                                    text_content=ai_response,
                                    success=True
                                )
                        else:
                            logger.warning("[TTS] 合成失败")
                        
                        audio_buffer.clear()
                        logger.info(f"[完成] 请求 #{request_count} 完成")
            
            elif msg_type == 0x03:  # 状态上报
                try:
                    status = json.loads(payload.decode('utf-8'))
                    logger.debug(f"[状态] {status}")
                    
                    if db and 'battery_level' in status:
                        await db.update_device_status(
                            device_id=device_id,
                            battery_level=status.get('battery_level'),
                            wifi_signal=status.get('wifi_signal'),
                            last_seen=datetime.now()
                        )
                except:
                    pass
            
            elif msg_type == 0x04:  # 唤醒事件
                logger.info(f"[唤醒] 清空缓冲区")
                audio_buffer.clear()
                
                if memory_mgr:
                    memory_mgr.clear_short_term(device_id)
    
    except WebSocketDisconnect:
        logger.info(f"[断开] {device_id}")
    except Exception as e:
        logger.error(f"[错误] {device_id}: {e}", exc_info=True)
    finally:
        manager.disconnect(device_id)
        
        if db:
            await db.update_device_status(device_id, last_seen=datetime.now())


def main():
    """启动服务器"""
    import uvicorn
    from config import get_config
    
    config = get_config()
    
    uvicorn.run(
        "server:app",
        host=config.HOST,
        port=config.PORT,
        reload=config.DEBUG,
        log_level=config.LOG_LEVEL.lower(),
        access_log=True,
        workers=1
    )


if __name__ == "__main__":
    main()
