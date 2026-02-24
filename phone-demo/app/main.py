"""
儿童智能语音玩具 - 重构版本
改进：
1. 使用单一事件循环，避免多线程异步问题
2. 完善的连接状态管理
3. 指数退避重连机制
4. 发送队列，避免并发写入

版本：2.0.0-rebuild
"""
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.clock import Clock
from kivy.properties import StringProperty
from kivy.metrics import dp
from kivy.core.text import LabelBase
import os
import sys
import time
import asyncio
import threading
import queue

# 配置日志
import logging
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime

LOG_DIR = os.path.join(os.path.dirname(__file__), 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

log_filename = datetime.now().strftime('app_%Y%m%d_%H%M%S.log')
log_filepath = os.path.join(LOG_DIR, log_filename)

app_logger = logging.getLogger("toyphone-rebuild")
app_logger.setLevel(logging.INFO)
app_logger.handlers.clear()

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
console_handler.setFormatter(console_formatter)

try:
    file_handler = TimedRotatingFileHandler(log_filepath, when='H', interval=1, backupCount=24, encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(console_formatter)
    app_logger.addHandler(file_handler)
except Exception as e:
    print(f"警告：无法创建日志文件：{e}")

app_logger.addHandler(console_handler)

app_logger.info("=" * 80)
app_logger.info(f"APP 启动 - 重构版本 v2.0.0")
app_logger.info("=" * 80)

# 注册中文字体
if sys.platform == 'win32':
    font_paths = [r'C:\Windows\Fonts\simhei.ttf', r'C:\Windows\Fonts\simsun.ttc']
    for font_path in font_paths:
        if os.path.exists(font_path):
            LabelBase.register(name='Chinese', fn_regular=font_path)
            break

# 配置
SERVER_HOST = "localhost"
SERVER_PORT = 8000
DEVICE_ID = "phone_001"
SAMPLE_RATE = 16000
CHANNELS = 1
CHUNK_SIZE = 1024


class ConnectionState:
    """连接状态枚举"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"


class WebSocketManager:
    """WebSocket 管理器 - 处理所有异步操作"""
    
    def __init__(self, on_message_callback, on_status_callback):
        self.ws = None
        self.session = None
        self.loop = None
        self.task = None
        self.running = False
        self.state = ConnectionState.DISCONNECTED
        
        # 回调
        self.on_message = on_message_callback
        self.on_status = on_status_callback
        
        # 发送队列
        self.send_queue = asyncio.Queue()
        
        # 重连配置
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        self.reconnect_delay = 1.0
        
        app_logger.info("WebSocketManager 初始化完成")
    
    async def _connect(self, url):
        """内部连接方法"""
        import aiohttp
        
        try:
            if self.session is None or self.session.closed:
                self.session = aiohttp.ClientSession()
            
            app_logger.info(f"正在连接：{url}")
            self._set_state(ConnectionState.CONNECTING)
            
            self.ws = await self.session.ws_connect(
                url,
                heartbeat=30,
                receive_timeout=60
            )
            
            self.reconnect_attempts = 0
            self._set_state(ConnectionState.CONNECTED)
            app_logger.info("连接成功")
            
            # 启动接收和发送任务
            self.task = asyncio.create_task(self._run_loop())
            
        except Exception as e:
            app_logger.error(f"连接失败：{e}")
            self._set_state(ConnectionState.DISCONNECTED)
            raise
    
    async def _run_loop(self):
        """主循环 - 处理接收和发送"""
        import aiohttp
        
        app_logger.info("WebSocket 主循环启动")
        
        try:
            while self.running and self.ws and not self.ws.closed:
                # 同时处理接收和发送
                receive_task = asyncio.create_task(self.ws.receive())
                send_task = asyncio.create_task(self._process_send_queue())
                
                done, pending = await asyncio.wait(
                    [receive_task, send_task],
                    return_when=asyncio.FIRST_COMPLETED
                )
                
                # 处理完成的任务
                if receive_task in done:
                    msg = receive_task.result()
                    await self._handle_message(msg)
                
                if send_task in done:
                    pass  # 发送完成
                
                # 取消未完成的任务
                for task in pending:
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
            
        except Exception as e:
            app_logger.error(f"主循环错误：{e}")
        finally:
            app_logger.info("WebSocket 主循环结束")
            self._set_state(ConnectionState.DISCONNECTED)
    
    async def _handle_message(self, msg):
        """处理接收到的消息"""
        import aiohttp
        
        if msg.type == aiohttp.WSMsgType.BINARY:
            data = msg.data
            if len(data) > 0:
                msg_type = data[0]
                payload = data[1:]
                app_logger.info(f"收到：0x{msg_type:02X}, {len(payload)} 字节")
                
                if self.on_message:
                    Clock.schedule_once(
                        lambda dt: self.on_message(msg_type, payload), 0
                    )
                    
        elif msg.type == aiohttp.WSMsgType.TEXT:
            app_logger.debug(f"收到文本：{msg.data}")
            
        elif msg.type == aiohttp.WSMsgType.CLOSED:
            app_logger.info("连接已关闭")
            self._set_state(ConnectionState.DISCONNECTED)
            
        elif msg.type == aiohttp.WSMsgType.ERROR:
            app_logger.error("WebSocket 错误")
            self._set_state(ConnectionState.DISCONNECTED)
    
    async def _process_send_queue(self):
        """处理发送队列"""
        try:
            data = await asyncio.wait_for(self.send_queue.get(), timeout=0.1)
            if self.ws and not self.ws.closed:
                await self.ws.send_bytes(data)
                app_logger.debug(f"发送成功：{len(data)} 字节")
        except asyncio.TimeoutError:
            pass
        except Exception as e:
            app_logger.error(f"发送失败：{e}")
            raise
    
    def _set_state(self, new_state):
        """设置连接状态"""
        if self.state != new_state:
            old_state = self.state
            self.state = new_state
            app_logger.info(f"状态变更：{old_state} -> {new_state}")
            
            if self.on_status:
                Clock.schedule_once(
                    lambda dt: self.on_status(new_state), 0
                )
    
    def connect(self, host, port, device_id):
        """启动连接（在非异步环境调用）"""
        url = f"ws://{host}:{port}/ws/audio/{device_id}"
        
        def run_loop():
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.running = True
            
            try:
                self.loop.run_until_complete(self._connect(url))
                self.loop.run_forever()
            except Exception as e:
                app_logger.error(f"连接异常：{e}")
                self._set_state(ConnectionState.DISCONNECTED)
            finally:
                self.running = False
                if self.loop and self.loop.is_running():
                    self.loop.stop()
                self.loop = None
        
        thread = threading.Thread(target=run_loop, daemon=True)
        thread.start()
        return thread
    
    def send(self, data: bytes):
        """发送数据到队列"""
        if self.state != ConnectionState.CONNECTED:
            app_logger.warning(f"无法发送：状态={self.state}")
            return False
        
        try:
            # 在线程安全的方式下添加到队列
            if self.loop and self.loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    self.send_queue.put(data),
                    self.loop
                )
                return True
        except Exception as e:
            app_logger.error(f"加入发送队列失败：{e}")
        
        return False
    
    def reconnect(self, host, port, device_id):
        """重新连接"""
        if self.state == ConnectionState.RECONNECTING:
            app_logger.info("已在重连中")
            return
        
        self._set_state(ConnectionState.RECONNECTING)
        
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            app_logger.error(f"达到最大重连次数 ({self.max_reconnect_attempts})")
            self._set_state(ConnectionState.DISCONNECTED)
            return
        
        delay = self.reconnect_delay * (2 ** self.reconnect_attempts)
        self.reconnect_attempts += 1
        
        app_logger.info(f"{delay:.1f}秒后尝试重连 ({self.reconnect_attempts}/{self.max_reconnect_attempts})")
        
        def do_reconnect():
            time.sleep(delay)
            if self.running:
                self.close()
                self.connect(host, port, device_id)
        
        thread = threading.Thread(target=do_reconnect, daemon=True)
        thread.start()
    
    def close(self):
        """关闭连接"""
        app_logger.info("关闭连接...")
        self.running = False
        
        if self.loop and self.loop.is_running():
            try:
                self.loop.call_soon_threadsafe(self.loop.stop)
            except Exception as e:
                app_logger.error(f"停止循环失败：{e}")
        
        if self.ws:
            try:
                if self.loop and self.loop.is_running():
                    asyncio.run_coroutine_threadsafe(self.ws.close(), self.loop)
            except Exception as e:
                app_logger.error(f"关闭 WebSocket 失败：{e}")
            self.ws = None
        
        self._set_state(ConnectionState.DISCONNECTED)
        app_logger.info("连接已关闭")


class ToyPhoneUI(BoxLayout):
    status_text = StringProperty("未连接")
    response_text = StringProperty("点击连接服务器开始使用")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.padding = dp(20)
        self.spacing = dp(20)

        # WebSocket 管理器
        self.ws_manager = WebSocketManager(
            on_message_callback=self._on_message,
            on_status_callback=self._on_status_change
        )
        
        # 录音相关
        self.audio = None
        self.audio_stream = None
        self.audio_buffer = bytearray()
        self.is_recording = False
        self.is_processing = False
        self.recording_start_time = 0

        self._build_ui()

        # 延迟检查服务器
        Clock.schedule_once(lambda dt: self._check_server(), 1.0)

    def _check_server(self):
        """检查服务器是否可连接"""
        app_logger.info("检查服务器状态...")
        try:
            import urllib.request
            url = f"http://{SERVER_HOST}:{SERVER_PORT}/health"
            response = urllib.request.urlopen(url, timeout=2)
            if response.status == 200:
                app_logger.info("✓ 服务器可访问")
                self.log("服务器已就绪")
            else:
                app_logger.warning(f"服务器异常：{response.status}")
                self.log(f"服务器异常：{response.status}")
        except Exception as e:
            app_logger.error(f"服务器不可访问：{e}")
            self.log("服务器未响应")

    def _build_ui(self):
        # 标题
        title = Label(
            text="儿童智能语音玩具 (重构版)",
            size_hint=(1, 0.1),
            font_size=dp(24),
            font_name='Chinese',
            bold=True
        )
        self.add_widget(title)

        # 状态显示
        self.status_label = Label(
            text=self.status_text,
            size_hint=(1, 0.08),
            font_size=dp(18),
            font_name='Chinese',
            color=(0.5, 0.5, 0.5, 1)
        )
        self.add_widget(self.status_label)

        # 对话显示区域
        self.response_label = Label(
            text=self.response_text,
            size_hint=(1, 0.4),
            font_size=dp(20),
            font_name='Chinese',
            valign='middle',
            halign='center',
            padding=(dp(20), dp(20))
        )
        self.add_widget(self.response_label)

        # 按钮区域
        btn_layout = BoxLayout(
            orientation='horizontal',
            size_hint=(1, 0.15),
            spacing=dp(20),
            padding=(dp(20), 0)
        )

        # 连接按钮
        self.connect_btn = Button(
            text="连接服务器",
            size_hint=(0.5, 1),
            font_size=dp(18),
            font_name='Chinese',
            background_color=(0.2, 0.6, 1, 1)
        )
        self.connect_btn.bind(on_press=self.on_connect_press)
        btn_layout.add_widget(self.connect_btn)

        # 录音按钮
        self.record_btn = Button(
            text="按住说话",
            size_hint=(0.5, 1),
            font_size=dp(18),
            font_name='Chinese',
            background_color=(0.3, 0.3, 0.3, 1),
            disabled=True
        )
        self.record_btn.bind(on_press=self.start_recording)
        self.record_btn.bind(on_release=self.stop_recording)
        btn_layout.add_widget(self.record_btn)

        self.add_widget(btn_layout)

        # 日志区域
        log_label = Label(
            text="日志:",
            size_hint=(1, 0.05),
            font_size=dp(14),
            font_name='Chinese',
            halign='left',
        )
        self.add_widget(log_label)

        self.log_text = Label(
            text="",
            size_hint=(1, 0.22),
            font_size=dp(12),
            font_name='Chinese',
            halign='left',
            valign='top',
        )
        self.add_widget(self.log_text)

    def log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        current_log = self.log_text.text
        new_log = f"[{timestamp}] {message}\n{current_log}"
        lines = new_log.split('\n')[:10]
        self.log_text.text = '\n'.join(lines)
        app_logger.info(f"[UI] {message}")

    def _on_status_change(self, new_state):
        """状态变更回调（在主线程调用）"""
        app_logger.info(f"UI 状态变更：{new_state}")
        
        if new_state == ConnectionState.CONNECTED:
            self.status_text = "已连接"
            self.status_label.text = "已连接"
            self.status_label.color = (0, 0.8, 0, 1)
            self.connect_btn.text = "断开连接"
            self.connect_btn.background_color = (1, 0.3, 0.3, 1)
            self.record_btn.disabled = False
            self.log("连接成功!")
            
        elif new_state == ConnectionState.DISCONNECTED:
            self.status_text = "未连接"
            self.status_label.text = "未连接"
            self.status_label.color = (0.5, 0.5, 0.5, 1)
            self.connect_btn.text = "连接服务器"
            self.connect_btn.background_color = (0.2, 0.6, 1, 1)
            self.record_btn.disabled = True
            self.response_text = "点击连接服务器开始使用"
            self.log("已断开")
            
        elif new_state == ConnectionState.CONNECTING:
            self.status_text = "连接中..."
            self.status_label.text = "连接中..."
            self.status_label.color = (1, 0.6, 0, 1)
            self.log("正在连接...")
            
        elif new_state == ConnectionState.RECONNECTING:
            self.status_text = "重连中..."
            self.status_label.text = "重连中..."
            self.status_label.color = (1, 0.6, 0, 1)
            self.log("正在重连...")

    def _on_message(self, msg_type, payload):
        """消息处理回调（在主线程调用）"""
        import json
        
        if msg_type == 0x01:  # JSON 响应
            try:
                response = json.loads(payload.decode('utf-8'))
                text = response.get('text', '')
                app_logger.info(f"AI 文本：{text}")
                self._show_response(text)
            except Exception as e:
                app_logger.error(f"解析失败：{e}")

        elif msg_type == 0x02:  # TTS 音频
            app_logger.info(f"收到 TTS 音频：{len(payload)} 字节")
            self._play_tts(payload)

        elif msg_type == 0x03:  # 流式文本片段
            try:
                chunk_data = json.loads(payload.decode('utf-8'))
                content = chunk_data.get('content', '')
                app_logger.debug(f"流式片段：{content}")
            except:
                pass

    def _show_response(self, text):
        """显示响应"""
        self.response_text = text
        self.log(f"AI: {text}")

    def _play_tts(self, audio_data):
        """播放 TTS 音频"""
        app_logger.info(f"播放 TTS: {len(audio_data)} 字节")
        self.log(f"播放 TTS...")

        try:
            from kivy.core.audio import SoundLoader
            import tempfile

            temp_file = tempfile.mktemp(suffix='.mp3')

            with open(temp_file, 'wb') as f:
                f.write(audio_data)

            app_logger.info(f"临时文件：{temp_file}")

            sound = SoundLoader.load(temp_file)
            if sound:
                sound.bind(on_stop=lambda instance: self._on_tts_stop(temp_file))
                sound.play()
                app_logger.info("开始播放 TTS")
                self.log("正在播放...")
            else:
                app_logger.error("无法加载音频文件")
                self.log("播放失败")
                try:
                    os.remove(temp_file)
                except:
                    pass

        except Exception as e:
            app_logger.error(f"播放失败：{e}")
            self.log(f"播放错误：{e}")

    def _on_tts_stop(self, temp_file):
        """TTS 播放完成回调"""
        app_logger.info("TTS 播放完成")
        self.log("播放完成")
        try:
            os.remove(temp_file)
        except:
            pass

    def on_connect_press(self, instance):
        """连接按钮按下"""
        app_logger.info("=" * 60)
        app_logger.info("连接按钮被按下")
        app_logger.info("=" * 60)

        if self.ws_manager.state == ConnectionState.CONNECTED:
            self.disconnect()
        else:
            self.connect()

    def connect(self):
        """连接服务器"""
        if self.ws_manager.state != ConnectionState.DISCONNECTED:
            app_logger.info(f"无法连接：当前状态={self.ws_manager.state}")
            return
        
        app_logger.info("开始连接...")
        self.ws_manager.connect(SERVER_HOST, SERVER_PORT, DEVICE_ID)

    def disconnect(self):
        """断开连接"""
        app_logger.info("断开连接...")
        self.ws_manager.close()

    def start_recording(self, instance):
        """开始录音"""
        app_logger.info("开始录音")

        if self.ws_manager.state != ConnectionState.CONNECTED:
            self.log("请先连接")
            return

        if self.is_processing:
            self.log("处理中，请稍后")
            return

        try:
            import pyaudio

            if self.audio is None:
                self.audio = pyaudio.PyAudio()
                app_logger.info("PyAudio 初始化成功")

            self.is_recording = True
            self.record_btn.text = "🔴 录音中..."
            self.record_btn.background_color = (1, 0.2, 0.2, 1)
            self.audio_buffer.clear()
            self.recording_start_time = time.time()

            def audio_callback(in_data, frame_count, time_info, status):
                if self.is_recording:
                    self.audio_buffer.extend(in_data)
                return (None, pyaudio.paContinue)

            self.audio_stream = self.audio.open(
                format=pyaudio.paInt16,
                channels=CHANNELS,
                rate=SAMPLE_RATE,
                input=True,
                frames_per_buffer=CHUNK_SIZE,
                stream_callback=audio_callback
            )
            self.audio_stream.start_stream()

            self.log("录音中...")
            app_logger.info("录音已开始")

        except Exception as e:
            app_logger.error(f"录音失败：{e}")
            self.log(f"麦克风错误：{e}")
            self.is_recording = False
            self.record_btn.text = "按住说话"
            self.record_btn.background_color = (0.3, 0.3, 0.3, 1)

    def stop_recording(self, instance):
        """停止录音并发送"""
        app_logger.info("停止录音")

        self.is_recording = False
        self.record_btn.text = "按住说话"
        self.record_btn.background_color = (0.3, 0.3, 0.3, 1)

        if self.audio_stream:
            try:
                self.audio_stream.stop_stream()
                self.audio_stream.close()
            except:
                pass

        duration = time.time() - self.recording_start_time
        app_logger.info(f"录音时长：{duration:.2f}秒，数据：{len(self.audio_buffer)}字节")

        if len(self.audio_buffer) > 0:
            self.log(f"发送 {len(self.audio_buffer)} 字节")
            self.is_processing = True
            self._send_audio()
        else:
            self.log("未检测到声音")

    def _send_audio(self):
        """发送音频数据"""
        if self.ws_manager.state != ConnectionState.CONNECTED:
            self.log("未连接，无法发送")
            app_logger.error("未连接，无法发送")
            self.is_processing = False
            return

        audio_data = bytes(self.audio_buffer)
        message = bytes([0x01]) + audio_data

        app_logger.info(f"发送：0x01 + {len(audio_data)}字节")
        
        if self.ws_manager.send(message):
            self.log("发送成功")
            app_logger.info("发送成功")
        else:
            self.log("发送失败")
            app_logger.error("发送失败")
        
        self.audio_buffer.clear()
        self.is_processing = False


class ToyPhoneApp(App):
    def build(self):
        self.title = "儿童智能语音玩具 (重构版)"
        app_logger.info("APP 启动")
        return ToyPhoneUI()

    def on_stop(self):
        """APP 停止时清理资源"""
        app_logger.info("APP 停止，清理资源...")

        if hasattr(self.root, 'ws_manager'):
            self.root.ws_manager.close()

        app_logger.info("APP 已停止")


if __name__ == '__main__':
    ToyPhoneApp().run()
