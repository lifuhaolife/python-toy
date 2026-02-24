"""
儿童智能语音玩具 - 服务器端
支持手机 APP 和 ESP32 设备连接

作者：Toy Project
版本：1.0.0
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
    """简易 AI 客户端"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = httpx.AsyncClient(timeout=30.0)
        self.system_prompt = """你是一个亲切友好的 AI 大姐姐，专门陪伴 3-12 岁的儿童。
你的特点是：
1. 语气温柔亲切，使用简单易懂的语言
2. 内容积极向上，传递正能量
3. 善于引导孩子学习和思考
4. 避免复杂词汇，多用比喻和故事
5. 注意安全问题，不涉及危险话题
6. 每次回复控制在 50 字以内，适合语音播放

请始终保持耐心和鼓励的态度，让孩子感受到关爱。"""
    
    async def chat(self, message: str, context: list = None) -> str:
        """发送对话请求"""
        messages = [
            {"role": "system", "content": self.system_prompt},
        ]
        
        if context:
            messages.extend(context[-5:])
        
        messages.append({"role": "user", "content": message})
        
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": "glm-4",
                "messages": messages,
                "max_tokens": 150,
                "temperature": 0.7
            }
            
            response = await self.client.post(
                "https://open.bigmodel.cn/api/paas/v4/chat/completions",
                headers=headers,
                json=data
            )
            response.raise_for_status()
            
            result = response.json()
            return result["choices"][0]["message"]["content"]
            
        except Exception as e:
            logger.error(f"AI 对话失败：{e}")
            return f"抱歉，我现在有点累，我们稍后再聊好吗？(错误：{str(e)[:50]})"
    
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
        if device_id in self.connections:
            try:
                await self.connections[device_id].send_bytes(data)
            except Exception as e:
                logger.error(f"发送数据失败：{e}")
                self.disconnect(device_id)
    
    async def send_json(self, device_id: str, data: dict):
        if device_id in self.connections:
            try:
                await self.connections[device_id].send_json(data)
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """生命周期管理"""
    global ai_client, tts_client, asr_client

    logger.info("=" * 80)
    logger.info("儿童智能语音玩具服务器 v1.0.0")
    logger.info("=" * 80)
    
    # 1. 初始化 AI 客户端
    logger.info("初始化 AI 客户端...")
    logger.info(f"AI_API_KEY: {AI_API_KEY[:10]}...{AI_API_KEY[-6:]}" if len(AI_API_KEY) > 20 else f"AI_API_KEY: ***")
    ai_client = SimpleAIClient(AI_API_KEY)
    
    # 2. 初始化 TTS 客户端
    logger.info("初始化 TTS 客户端...")
    tts_client = SimpleTTSClient()
    
    # 3. 初始化 ASR 客户端（直接加载本地模型）
    logger.info("初始化 ASR 客户端（语音识别）...")
    asr_client = SimpleASRClient()
    
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
    if asr_client.model:
        logger.info(f"ASR 客户端：已初始化 (Whisper 模型已加载)")
    else:
        logger.error(f"ASR 客户端：已初始化 (模型未加载，语音识别不可用)")
    logger.info(f"服务器地址：http://{HOST}:{PORT}")
    logger.info("=" * 80)

    yield

    if ai_client:
        await ai_client.close()
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
    WebSocket 音频接口
    
    优化:
    1. 降低音频阈值，减少等待时间
    2. 并行处理 TTS 和响应
    3. 支持连续对话
    """
    logger.info("=" * 80)
    logger.info(f"[WebSocket] 新连接：{device_id}")
    logger.info("=" * 80)

    await manager.connect(ws, device_id)

    audio_buffer = bytearray()
    message_count = 0
    request_count = 0
    
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
                    logger.info("=" * 60)
                    logger.info(f"[处理] 请求 #{request_count} ({len(audio_buffer)/SAMPLE_RATE:.2f}秒音频)")
                    logger.info("=" * 60)

                    # 1. 语音识别 (ASR) - 真实识别
                    logger.info("[1/4] ASR 语音识别...")
                    user_text = asr_client.transcribe(bytes(audio_buffer))
                    
                    # 如果识别结果为空，跳过本次请求
                    if not user_text:
                        logger.warning("[ASR] 未识别到有效语音，跳过本次请求")
                        audio_buffer.clear()
                        continue
                    
                    logger.info(f"[ASR] ✅ 识别结果：{user_text}")

                    # 2. AI 对话（与 TTS 并行）
                    logger.info("[2/4] AI 对话...")
                    context = manager.get_context(device_id)
                    ai_response = await ai_client.chat(user_text, context)
                    logger.info(f"[AI] ✅ {ai_response}")
                    manager.add_context(device_id, "user", user_text)
                    manager.add_context(device_id, "assistant", ai_response)

                    # 3. 发送文本响应（立即发送，不等待 TTS）
                    logger.info("[3/4] 发送文本响应...")
                    await manager.send_json(device_id, {
                        "type": "response",
                        "text": ai_response
                    })
                    logger.info(f"[响应] ✅ 已发送")

                    # 4. TTS 合成（异步）
                    logger.info("[4/4] TTS 合成...")
                    tts_audio = await tts_client.synthesize(ai_response)
                    if tts_audio:
                        logger.info(f"[TTS] ✅ {len(tts_audio)} 字节")
                        await manager.send_bytes(device_id, bytes([0x02]) + tts_audio)
                    else:
                        logger.warning(f"[TTS] ❌ 失败")

                    # 清空缓冲区，准备下一次对话
                    audio_buffer.clear()
                    logger.info(f"[完成] 请求 #{request_count} 完成")
                    logger.info("=" * 60)

            elif msg_type == 0x03:  # 状态上报
                try:
                    status = json.loads(payload.decode('utf-8'))
                    logger.debug(f"[状态] {status}")
                except:
                    pass

            elif msg_type == 0x04:  # 唤醒事件
                logger.info(f"[唤醒] 清空缓冲区")
                audio_buffer.clear()

    except WebSocketDisconnect:
        logger.info(f"[断开] {device_id}")
    except Exception as e:
        logger.error(f"[错误] {device_id}: {e}", exc_info=True)
    finally:
        manager.disconnect(device_id)


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
