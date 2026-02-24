"""
儿童智能语音玩具 - 服务器端
支持手机 APP 和 ESP32 设备连接

作者：Toy Project
版本：2.0.0 (支持流式响应和数据库记忆)
"""
import os
import sys
import json
import asyncio
import logging
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import httpx

# 修复 Windows 控制台编码问题
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# 导入数据库和记忆管理
from database import get_database, Database
from memory_manager import get_memory_manager, MemoryManager

# 创建日志文件夹
LOG_DIR = os.path.join(os.path.dirname(__file__), 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

# 配置日志 - 同时输出到控制台和文件
log_filename = datetime.now().strftime('server_%Y%m%d_%H%M%S.log')
log_filepath = os.path.join(LOG_DIR, log_filename)

# 创建 logger
logger = logging.getLogger("toy-server")
logger.setLevel(logging.INFO)

# 清除现有 handler
logger.handlers.clear()

# 控制台 handler
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
console_handler.setFormatter(console_formatter)

# 文件 handler (按时间分割)
file_handler = TimedRotatingFileHandler(
    log_filepath,
    when='H',  # 每小时分割
    interval=1,
    backupCount=24,  # 保留 24 个文件
    encoding='utf-8'
)
file_handler.setLevel(logging.INFO)
file_formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
file_handler.setFormatter(file_formatter)

# 添加 handler
logger.addHandler(console_handler)
logger.addHandler(file_handler)

# 启动日志
logger.info("=" * 80)
logger.info(f"日志文件：{log_filepath}")
logger.info("=" * 80)

# 加载环境变量（从上级目录 phone-demo/.env）
env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(env_path)

# 配置
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", 8000))
DEBUG = os.getenv("DEBUG", "true").lower() == "true"
AI_API_KEY = os.getenv("AI_API_KEY", "")

# 音频配置
SAMPLE_RATE = 16000


class SimpleAIClient:
    """简易 AI 客户端（支持流式响应）"""

    def __init__(self, api_key: str, db=None):
        self.api_key = api_key
        self.client = httpx.AsyncClient(timeout=60.0)
        self.db = db
        self.system_prompt = """你是一个亲切友好的 AI 大姐姐，专门陪伴 3-12 岁的儿童。
你的特点是：
1. 语气温柔亲切，使用简单易懂的语言
2. 内容积极向上，传递正能量
3. 善于引导孩子学习和思考
4. 避免复杂词汇，多用比喻和故事
5. 注意安全问题，不涉及危险话题
6. 每次回复控制在 50 字以内，适合语音播放

请始终保持耐心和鼓励的态度，让孩子感受到关爱。"""

    async def chat(self, message: str, context: list = None, device_id: str = None, session_id: str = None) -> str:
        """发送对话请求（非流式，完整记录）"""
        import uuid
        from datetime import datetime
        
        request_id = str(uuid.uuid4())
        request_start_time = datetime.now()
        
        messages = [
            {"role": "system", "content": self.system_prompt},
        ]

        if context:
            messages.extend(context[-5:])

        messages.append({"role": "user", "content": message})

        # 构建请求数据
        request_data = {
            "model": "glm-4",
            "messages": messages,
            "max_tokens": 150,
            "temperature": 0.7
        }
        
        api_endpoint = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
        
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            response = await self.client.post(
                api_endpoint,
                headers=headers,
                json=request_data
            )
            
            request_end_time = datetime.now()
            duration_ms = int((request_end_time - request_start_time).total_seconds() * 1000)
            
            response.raise_for_status()
            result = response.json()
            ai_content = result["choices"][0]["message"]["content"]
            
            # 提取使用量
            usage = result.get("usage", {})
            total_tokens = usage.get("total_tokens", 0)
            prompt_tokens = usage.get("prompt_tokens", 0)
            completion_tokens = usage.get("completion_tokens", 0)
            finish_reason = result["choices"][0].get("finish_reason", "stop")
            
            # 记录到对话表
            if self.db:
                conversation_id = await self.db.save_conversation(
                    device_id=device_id,
                    session_id=session_id,
                    user_message=message,
                    ai_message=ai_content,
                    duration_ms=duration_ms,
                    total_tokens=total_tokens,
                    context_messages=messages,
                    request_data=request_data,
                    response_data=result,
                    model_name="glm-4",
                    temperature=0.7,
                    max_tokens=150,
                    finish_reason=finish_reason,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    is_stream=False
                )
                
                # 记录 API 日志
                await self.db.log_ai_request(
                    request_id=request_id,
                    device_id=device_id,
                    session_id=session_id,
                    conversation_id=conversation_id,
                    request_body=request_data,
                    response_body=result,
                    response_status=response.status_code,
                    duration_ms=duration_ms,
                    is_success=True,
                    model="glm-4",
                    endpoint=api_endpoint,
                    api_key_prefix=self.api_key[:10] + "...",
                    request_messages_count=len(messages),
                    request_system_prompt=self.system_prompt,
                    request_user_message=message,
                    request_context=context,
                    response_content=ai_content,
                    response_finish_reason=finish_reason,
                    usage_total_tokens=total_tokens,
                    usage_prompt_tokens=prompt_tokens,
                    usage_completion_tokens=completion_tokens,
                    request_start_time=request_start_time,
                    request_end_time=request_end_time
                )
            
            return ai_content

        except Exception as e:
            request_end_time = datetime.now()
            duration_ms = int((request_end_time - request_start_time).total_seconds() * 1000)
            
            logger.error(f"AI 对话失败：{e}")
            
            # 记录错误
            if self.db:
                await self.db.log_ai_request(
                    request_id=request_id,
                    device_id=device_id,
                    session_id=session_id,
                    request_body=request_data,
                    response_status=getattr(e, 'response', None).status_code if hasattr(e, 'response') else 0,
                    duration_ms=duration_ms,
                    is_success=False,
                    error_message=str(e),
                    error_type=type(e).__name__,
                    model="glm-4",
                    endpoint=api_endpoint,
                    api_key_prefix=self.api_key[:10] + "...",
                    request_messages_count=len(messages),
                    request_system_prompt=self.system_prompt,
                    request_user_message=message,
                    request_context=context,
                    request_start_time=request_start_time,
                    request_end_time=request_end_time
                )
            
            return f"抱歉，我现在有点累，我们稍后再聊好吗？(错误：{str(e)[:50]})"

    async def chat_stream(self, message: str, context: list = None, device_id: str = None, session_id: str = None):
        """
        发送对话请求（流式响应，完整记录）

        Yields:
            生成的文本片段
        """
        import uuid
        from datetime import datetime
        
        request_id = str(uuid.uuid4())
        request_start_time = datetime.now()
        
        messages = [
            {"role": "system", "content": self.system_prompt},
        ]

        if context:
            messages.extend(context[-5:])

        messages.append({"role": "user", "content": message})

        # 构建请求数据
        request_data = {
            "model": "glm-4",
            "messages": messages,
            "max_tokens": 150,
            "temperature": 0.7,
            "stream": True
        }
        
        api_endpoint = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
        
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

            # 使用 stream 接口
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
                                    yield content  # 实时返回片段
                                
                                # 提取结束原因
                                if "finish_reason" in data_json["choices"][0]:
                                    finish_reason = data_json["choices"][0]["finish_reason"]
                                    
                                # 提取使用量（通常在最后一个 chunk）
                                if "usage" in data_json:
                                    usage = data_json["usage"]
                                    
                        except json.JSONDecodeError:
                            continue

            request_end_time = datetime.now()
            duration_ms = int((request_end_time - request_start_time).total_seconds() * 1000)
            
            # 记录到数据库
            if self.db:
                conversation_id = await self.db.save_conversation(
                    device_id=device_id,
                    session_id=session_id,
                    user_message=message,
                    ai_message=full_content,
                    duration_ms=duration_ms,
                    total_tokens=usage.get("total_tokens", 0),
                    context_messages=messages,
                    request_data=request_data,
                    response_data={"choices": [{"message": {"content": full_content}}], "usage": usage},
                    model_name="glm-4",
                    temperature=0.7,
                    max_tokens=150,
                    finish_reason=finish_reason or "stop",
                    prompt_tokens=usage.get("prompt_tokens", 0),
                    completion_tokens=usage.get("completion_tokens", 0),
                    is_stream=True
                )
                
                # 记录 API 日志
                await self.db.log_ai_request(
                    request_id=request_id,
                    device_id=device_id,
                    session_id=session_id,
                    conversation_id=conversation_id,
                    request_body=request_data,
                    response_body={"content": full_content, "usage": usage},
                    response_status=response_status,
                    duration_ms=duration_ms,
                    is_success=True,
                    model="glm-4",
                    endpoint=api_endpoint,
                    api_key_prefix=self.api_key[:10] + "...",
                    request_messages_count=len(messages),
                    request_system_prompt=self.system_prompt,
                    request_user_message=message,
                    request_context=context,
                    response_content=full_content,
                    response_finish_reason=finish_reason or "stop",
                    usage_total_tokens=usage.get("total_tokens", 0),
                    usage_prompt_tokens=usage.get("prompt_tokens", 0),
                    usage_completion_tokens=usage.get("completion_tokens", 0),
                    is_stream=True,
                    stream_chunks_count=stream_chunks,
                    request_start_time=request_start_time,
                    request_end_time=request_end_time
                )

        except Exception as e:
            request_end_time = datetime.now()
            duration_ms = int((request_end_time - request_start_time).total_seconds() * 1000)
            
            logger.error(f"AI 流式对话失败：{e}")
            
            # 记录错误
            if self.db:
                await self.db.log_ai_request(
                    request_id=request_id,
                    device_id=device_id,
                    session_id=session_id,
                    request_body=request_data,
                    response_status=response_status,
                    duration_ms=duration_ms,
                    is_success=False,
                    error_message=str(e),
                    error_type=type(e).__name__,
                    model="glm-4",
                    endpoint=api_endpoint,
                    api_key_prefix=self.api_key[:10] + "...",
                    request_messages_count=len(messages),
                    request_system_prompt=self.system_prompt,
                    request_user_message=message,
                    request_context=context,
                    is_stream=True,
                    stream_chunks_count=stream_chunks,
                    request_start_time=request_start_time,
                    request_end_time=request_end_time
                )
            
            yield f"抱歉，我现在有点累。(错误：{str(e)[:30]})"

    async def close(self):
        await self.client.aclose()


class SimpleTTSClient:
    """简易 TTS 客户端（使用 edge-tts 免费）"""
    
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
            logger.error(f"TTS 合成失败：{e}")
            return b''


class SimpleASRClient:
    """语音识别客户端（使用 Whisper 真实识别）"""
    
    def __init__(self):
        self.model = None
        self.model_path = os.path.join(os.path.dirname(__file__), 'models', 'whisper-tiny')
        logger.info("ASR 客户端：已初始化")
        logger.info(f"模型路径：{self.model_path}")
        
        # 直接加载模型（不自动下载）
        self._load_model()
    
    def _load_model(self):
        """加载本地 Whisper 模型"""
        try:
            from faster_whisper import WhisperModel
            
            # 检查本地是否有模型
            if not os.path.exists(self.model_path):
                logger.error(f"模型不存在：{self.model_path}")
                logger.error("请先下载 Whisper 模型:")
                logger.error("  1. 运行：python download_whisper_model.py")
                logger.error("  2. 或手动下载模型到：models/whisper-tiny/")
                return
            
            # 加载模型
            self.model = WhisperModel(
                self.model_path,
                device="cpu",
                compute_type="int8"
            )
            logger.info("Whisper 模型加载成功")
            
        except Exception as e:
            logger.error(f"模型加载失败：{e}")
            self.model = None
    
    def transcribe(self, audio_data: bytes) -> str:
        """
        真实语音识别
        
        Args:
            audio_data: PCM 音频数据 (16kHz, 16bit, 单声道)
            
        Returns:
            识别的文本（如果识别失败返回空字符串）
        """
        # 如果模型未加载，直接返回空字符串
        if self.model is None:
            logger.error("模型未加载，无法识别语音")
            return ""
        
        try:
            # 将字节转换为 float32 数组
            import numpy as np
            audio_array = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
            
            logger.info(f"开始语音识别，音频长度：{len(audio_array)/16000:.2f}秒")
            
            # 使用 Whisper 识别
            segments, info = self.model.transcribe(
                audio_array,
                language="zh",
                vad_filter=True,  # 语音活动检测
                vad_parameters=dict(
                    threshold=0.5,
                    min_silence_duration_ms=500
                )
            )
            
            # 收集所有识别结果
            text = ""
            for segment in segments:
                text += segment.text
            
            text = text.strip()
            
            if text:
                logger.info(f"[ASR] ✅ 识别结果：{text}")
            else:
                logger.warning("[ASR] 未识别到有效语音（返回空字符串）")
            
            return text  # 返回真实识别结果，可能为空
            
        except Exception as e:
            logger.error(f"语音识别失败：{e}")
            return ""  # 失败返回空字符串


class ConnectionManager:
    """WebSocket 连接管理器"""

    def __init__(self):
        self.connections: dict = {}
        self.contexts: dict = {}

    async def connect(self, ws: WebSocket, device_id: str):
        await ws.accept()
        self.connections[device_id] = ws
        self.contexts[device_id] = []
        logger.info(f"[WebSocket] 新连接：{device_id}")

    def disconnect(self, device_id: str):
        if device_id in self.connections:
            del self.connections[device_id]
        if device_id in self.contexts:
            del self.contexts[device_id]
        logger.info(f"[WebSocket] 连接断开：{device_id}")

    async def send_bytes(self, device_id: str, data: bytes):
        """发送二进制数据（带连接状态检查）"""
        if device_id not in self.connections:
            logger.warning(f"发送失败：设备 {device_id} 未连接")
            return
        
        ws = self.connections[device_id]
        
        # 检查连接是否已关闭
        try:
            if ws.client_state.name == 'DISCONNECTED':
                logger.warning(f"发送失败：设备 {device_id} 已断开")
                self.disconnect(device_id)
                return
        except Exception:
            # 如果无法获取状态，尝试发送，失败则断开
            pass
        
        try:
            await ws.send_bytes(data)
        except Exception as e:
            logger.error(f"发送数据失败：{e}")
            self.disconnect(device_id)

    async def send_json(self, device_id: str, data: dict):
        """发送 JSON 数据（带连接状态检查）"""
        if device_id not in self.connections:
            logger.warning(f"发送 JSON 失败：设备 {device_id} 未连接")
            return
        
        ws = self.connections[device_id]
        
        # 检查连接是否已关闭
        try:
            if ws.client_state.name == 'DISCONNECTED':
                logger.warning(f"发送 JSON 失败：设备 {device_id} 已断开")
                self.disconnect(device_id)
                return
        except Exception:
            # 如果无法获取状态，尝试发送，失败则断开
            pass
        
        try:
            await ws.send_json(data)
        except Exception as e:
            logger.error(f"发送 JSON 失败：{e}")
            self.disconnect(device_id)
    
    def add_context(self, device_id: str, role: str, content: str):
        if device_id not in self.contexts:
            self.contexts[device_id] = []
        self.contexts[device_id].append({"role": role, "content": content})
        if len(self.contexts[device_id]) > 20:
            self.contexts[device_id] = self.contexts[device_id][-20:]
    
    def get_context(self, device_id: str) -> list:
        return self.contexts.get(device_id, [])


# 全局对象
manager = ConnectionManager()
ai_client = None
tts_client = None
asr_client = None
db: Database = None
memory_mgr: MemoryManager = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """生命周期管理"""
    global ai_client, tts_client, asr_client, db, memory_mgr

    logger.info("=" * 80)
    logger.info("儿童智能语音玩具服务器 v2.0.0")
    logger.info("=" * 80)

    # 打印数据库配置
    from db_config import DBConfig
    DBConfig.print_config()

    # 0. 自动检查和升级数据库
    logger.info("检查数据库版本...")
    from db_migrate_auto import check_database_version
    db_upgraded = await check_database_version()
    
    # 初始化数据库连接
    logger.info("初始化数据库连接...")
    db = get_database()
    await db.connect()
    logger.info(f"数据库连接成功 (类型：{db.db_type})")

    # 1. 初始化 AI 客户端
    logger.info("初始化 AI 客户端...")
    logger.info(f"AI_API_KEY: {AI_API_KEY[:10]}...{AI_API_KEY[-6:]}" if len(AI_API_KEY) > 20 else f"AI_API_KEY: ***")
    ai_client = SimpleAIClient(AI_API_KEY, db=db)

    # 2. 初始化 TTS 客户端
    logger.info("初始化 TTS 客户端...")
    tts_client = SimpleTTSClient()

    # 3. 初始化 ASR 客户端（直接加载本地模型）
    logger.info("初始化 ASR 客户端（语音识别）...")
    asr_client = SimpleASRClient()

    # 4. 初始化记忆管理器
    logger.info("初始化记忆管理器...")
    memory_mgr = get_memory_manager(db)

    # 检查模型加载状态
    if asr_client.model:
        logger.info("✅ Whisper 模型已加载")
    else:
        logger.error("❌ Whisper 模型加载失败")
        logger.error("语音识别功能将不可用")
        logger.error("请运行：python download_whisper_model.py 下载模型")

    logger.info("=" * 80)
    logger.info(f"AI 客户端：已初始化")
    logger.info(f"TTS 客户端：已初始化 (edge-tts)")
    logger.info(f"数据库：已连接")
    logger.info(f"记忆管理器：已初始化")
    if asr_client.model:
        logger.info(f"ASR 客户端：已初始化 (Whisper 模型已加载)")
    else:
        logger.error(f"ASR 客户端：已初始化 (模型未加载，语音识别不可用)")
    logger.info(f"服务器地址：http://{HOST}:{PORT}")
    logger.info("=" * 80)

    yield

    # 关闭资源
    if ai_client:
        await ai_client.close()
    if db:
        await db.close()
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
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "connections": len(manager.connections)
    }


@app.websocket("/ws/audio/{device_id}")
async def websocket_audio(ws: WebSocket, device_id: str):
    """
    WebSocket 音频接口（支持流式响应）

    消息类型:
    - 0x01: 音频数据
    - 0x02: TTS 音频
    - 0x03: 流式文本片段
    - 0x04: 唤醒事件
    - 0x05: 状态上报
    """
    logger.info("=" * 80)
    logger.info(f"[WebSocket] 新连接：{device_id}")
    logger.info("=" * 80)

    await manager.connect(ws, device_id)

    # 注册设备
    if db:
        await db.register_device(device_id, device_type="phone")
        await db.update_device_status(device_id, last_seen=datetime.now())

    audio_buffer = bytearray()
    message_count = 0
    request_count = 0
    session_id = f"{device_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

    # 优化：降低音频阈值到 1 秒
    min_audio_duration = 1.0  # 秒
    min_audio_bytes = int(SAMPLE_RATE * min_audio_duration * 2)  # 16bit = 2 字节

    try:
        while True:
            data = await ws.receive_bytes()
            message_count += 1

            if len(data) == 0:
                continue

            msg_type = data[0]
            payload = data[1:]

            logger.info(f"[消息 #{message_count}] 来自 {device_id}: 0x{msg_type:02X}, {len(payload)} 字节")

            if msg_type == 0x01:  # 音频数据
                audio_buffer.extend(payload)

                # 优化：降低到 1 秒音频就开始处理
                if len(audio_buffer) >= min_audio_bytes:
                    request_count += 1
                    start_time = datetime.now()
                    logger.info("=" * 60)
                    logger.info(f"[处理] 请求 #{request_count} ({len(audio_buffer)/SAMPLE_RATE:.2f}秒音频)")
                    logger.info("=" * 60)

                    # 1. 语音识别 (ASR) - 真实识别
                    logger.info("[1/5] ASR 语音识别...")
                    user_text = asr_client.transcribe(bytes(audio_buffer))
                    asr_duration = (datetime.now() - start_time).total_seconds() * 1000

                    # 记录 ASR 日志
                    if db:
                        await db.log_asr(
                            device_id=device_id,
                            audio_duration_ms=int(len(audio_buffer)/SAMPLE_RATE*1000),
                            recognized_text=user_text,
                            success=bool(user_text)
                        )

                    # 如果识别结果为空，跳过本次请求
                    if not user_text:
                        logger.warning("[ASR] 未识别到有效语音，跳过本次请求")
                        audio_buffer.clear()
                        continue

                    logger.info(f"[ASR] ✅ 识别结果：{user_text}")

                    # 2. 获取对话上下文（包含历史记忆）
                    logger.info("[2/5] 构建对话上下文...")
                    if memory_mgr:
                        context = await memory_mgr.build_context(device_id)
                    else:
                        context = manager.get_context(device_id)

                    # 3. AI 对话（流式响应）
                    logger.info("[3/5] AI 对话（流式）...")
                    ai_response = ""
                    
                    # 发送流式响应开始标记
                    await manager.send_json(device_id, {
                        "type": "stream_start",
                        "message_id": request_count
                    })

                    # 流式接收 AI 响应
                    async for chunk in ai_client.chat_stream(user_text, context, device_id=device_id, session_id=session_id):
                        ai_response += chunk
                        # 实时发送文本片段
                        await manager.send_json(device_id, {
                            "type": "stream_chunk",
                            "content": chunk
                        })

                    # 发送流式响应结束标记
                    await manager.send_json(device_id, {
                        "type": "stream_end",
                        "message_id": request_count,
                        "full_text": ai_response
                    })

                    logger.info(f"[AI] ✅ {ai_response}")
                    ai_duration = (datetime.now() - start_time).total_seconds() * 1000 - asr_duration

                    # 更新上下文和记忆
                    manager.add_context(device_id, "user", user_text)
                    manager.add_context(device_id, "assistant", ai_response)

                    # 保存到数据库
                    if memory_mgr:
                        await memory_mgr.save_conversation(
                            device_id=device_id,
                            session_id=session_id,
                            user_message=user_text,
                            ai_message=ai_response,
                            duration_ms=int(ai_duration)
                        )

                    # 4. 发送完整文本响应（兼容旧客户端）
                    logger.info("[4/5] 发送完整响应...")
                    await manager.send_json(device_id, {
                        "type": "response",
                        "text": ai_response
                    })

                    # 5. TTS 合成（异步）
                    logger.info("[5/5] TTS 合成...")
                    tts_audio = await tts_client.synthesize(ai_response)
                    tts_duration = (datetime.now() - start_time).total_seconds() * 1000 - ai_duration

                    if tts_audio:
                        logger.info(f"[TTS] ✅ {len(tts_audio)} 字节")
                        await manager.send_bytes(device_id, bytes([0x02]) + tts_audio)
                        
                        # 记录 TTS 日志
                        if db:
                            await db.log_tts(
                                device_id=device_id,
                                text_content=ai_response,
                                audio_duration_ms=int(tts_duration),
                                file_size=len(tts_audio),
                                success=True
                            )
                    else:
                        logger.warning(f"[TTS] ❌ 失败")
                        if db:
                            await db.log_tts(
                                device_id=device_id,
                                text_content=ai_response,
                                success=False,
                                error_message="TTS 合成失败"
                            )

                    # 清空缓冲区，准备下一次对话
                    audio_buffer.clear()
                    total_duration = (datetime.now() - start_time).total_seconds()
                    logger.info(f"[完成] 请求 #{request_count} 完成 (总耗时：{total_duration:.2f}秒)")
                    logger.info("=" * 60)

            elif msg_type == 0x03:  # 状态上报
                try:
                    status = json.loads(payload.decode('utf-8'))
                    logger.debug(f"[状态] {status}")
                    
                    # 更新设备状态
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
                
                # 清空短期记忆，开始新对话
                if memory_mgr:
                    memory_mgr.clear_short_term(device_id)

    except WebSocketDisconnect:
        logger.info(f"[断开] {device_id}")
    except Exception as e:
        logger.error(f"[错误] {device_id}: {e}", exc_info=True)
    finally:
        manager.disconnect(device_id)
        
        # 更新设备离线状态
        if db:
            await db.update_device_status(device_id, last_seen=datetime.now())


# 音频配置
SAMPLE_RATE = 16000


def main():
    """启动服务器"""
    import uvicorn
    uvicorn.run(
        "server:app",
        host=HOST,
        port=PORT,
        reload=DEBUG,
        log_level="info"
    )


if __name__ == "__main__":
    main()
