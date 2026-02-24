"""
儿童智能语音玩具 - 稳定版本
使用同步方式处理 WebSocket，避免异步问题

版本：1.2.0-stable
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
import threading

# 配置日志
import logging
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime

LOG_DIR = os.path.join(os.path.dirname(__file__), 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

log_filename = datetime.now().strftime('app_%Y%m%d_%H%M%S.log')
log_filepath = os.path.join(LOG_DIR, log_filename)

app_logger = logging.getLogger("toyphone-stable")
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
app_logger.info(f"APP 启动 - 稳定版本 v1.2.0")
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


class ToyPhoneUI(BoxLayout):
    status_text = StringProperty("未连接")
    response_text = StringProperty("点击连接服务器开始使用")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.padding = dp(20)
        self.spacing = dp(20)
        
        # WebSocket 相关（同步）
        self.ws = None
        self.session = None
        self.ws_lock = threading.Lock()  # 线程锁
        self.is_connected = False
        
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
            text="儿童智能语音玩具 (稳定版)",
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

    def on_connect_press(self, instance):
        """连接按钮按下"""
        app_logger.info("=" * 60)
        app_logger.info("连接按钮被按下")
        app_logger.info("=" * 60)
        
        if self.is_connected:
            self.disconnect()
        else:
            self.connect()

    def connect(self):
        """连接服务器（同步方式）"""
        app_logger.info("开始连接...")
        self.log("正在连接...")
        
        def do_connect():
            import aiohttp
            import asyncio
            
            async def _connect():
                try:
                    app_logger.info("创建 session...")
                    self.session = aiohttp.ClientSession()
                    
                    url = f"ws://{SERVER_HOST}:{SERVER_PORT}/ws/audio/{DEVICE_ID}"
                    app_logger.info(f"连接：{url}")
                    
                    ws = await self.session.ws_connect(url, timeout=5.0)
                    
                    # 使用锁保护 WebSocket 对象
                    with self.ws_lock:
                        self.ws = ws
                    
                    app_logger.info("连接成功!")
                    
                    # 更新 UI
                    Clock.schedule_once(lambda dt: self._on_connected(), 0)
                    
                    # 启动接收循环
                    await self._receive_loop()
                    
                except Exception as e:
                    app_logger.error(f"连接失败：{e}")
                    Clock.schedule_once(lambda dt: self._on_connect_error(str(e)), 0)
                finally:
                    if self.session:
                        await self.session.close()
            
            asyncio.run(_connect())
        
        # 在后台线程运行
        thread = threading.Thread(target=do_connect, daemon=True)
        thread.start()

    def _on_connected(self):
        """连接成功回调"""
        app_logger.info("连接成功回调")
        
        self.is_connected = True
        self.status_text = "已连接"
        self.status_label.text = "已连接"
        self.status_label.color = (0, 0.8, 0, 1)
        self.connect_btn.text = "断开连接"
        self.connect_btn.background_color = (1, 0.3, 0.3, 1)
        self.record_btn.disabled = False
        self.log("连接成功!")
        
        with self.ws_lock:
            app_logger.info(f"WebSocket 对象：{self.ws}")

    def _on_connect_error(self, error):
        """连接错误回调"""
        app_logger.error(f"连接错误：{error}")
        
        self.is_connected = False
        self.status_text = "连接失败"
        self.status_label.text = "连接失败"
        self.status_label.color = (1, 0, 0, 1)
        self.connect_btn.text = "重新连接"
        self.connect_btn.background_color = (0.2, 0.6, 1, 1)
        
        self.log(f"错误：{error}")
        self.log("请检查服务器")

    async def _receive_loop(self):
        """接收消息循环"""
        import aiohttp
        
        app_logger.info("开始接收消息...")
        try:
            while True:
                with self.ws_lock:
                    ws = self.ws
                
                if not ws or ws.closed:
                    app_logger.info("WebSocket 已关闭，退出接收")
                    break
                
                msg = await ws.receive()
                
                if msg.type == aiohttp.WSMsgType.BINARY:
                    data = msg.data
                    msg_type = data[0]
                    payload = data[1:]
                    
                    app_logger.info(f"收到：0x{msg_type:02X}, {len(payload)} 字节")
                    
                    if msg_type == 0x01:  # JSON 响应
                        import json
                        try:
                            response = json.loads(payload.decode('utf-8'))
                            text = response.get('text', '')
                            app_logger.info(f"AI 文本：{text}")
                            Clock.schedule_once(lambda dt: self._show_response(text), 0)
                        except Exception as e:
                            app_logger.error(f"解析失败：{e}")
                    
                    elif msg_type == 0x02:  # TTS 音频
                        app_logger.info(f"收到 TTS 音频：{len(payload)} 字节")
                        Clock.schedule_once(lambda dt: self._play_tts(payload), 0)
                            
                elif msg.type == aiohttp.WSMsgType.CLOSED:
                    app_logger.info("连接已关闭")
                    break
                    
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    app_logger.error(f"WebSocket 错误")
                    break
                    
        except Exception as e:
            app_logger.error(f"接收错误：{e}")
        
        app_logger.info("接收循环结束")
        Clock.schedule_once(lambda dt: self.disconnect(), 0)

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
            
            # 创建临时文件（edge-tts 输出是 MP3 格式）
            temp_file = tempfile.mktemp(suffix='.mp3')
            
            with open(temp_file, 'wb') as f:
                f.write(audio_data)
            
            app_logger.info(f"临时文件：{temp_file}")
            
            # 加载并播放
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

    def start_recording(self, instance):
        """开始录音"""
        app_logger.info("开始录音")
        
        if not self.is_connected:
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
        """发送音频数据（同步方式）"""
        # 发送前检查
        if not self.is_connected:
            self.log("未连接")
            app_logger.error("未连接，无法发送")
            return
        
        with self.ws_lock:
            ws = self.ws
        
        if not ws:
            self.log("WebSocket 未初始化")
            app_logger.error("WebSocket 为 None")
            return
        
        if ws.closed:
            self.log("连接已断开")
            app_logger.error("WebSocket 已关闭")
            return
        
        def do_send():
            import asyncio
            
            async def _send():
                try:
                    audio_data = bytes(self.audio_buffer)
                    message = bytes([0x01]) + audio_data
                    
                    app_logger.info(f"发送：0x01 + {len(audio_data)}字节")
                    await ws.send_bytes(message)
                    
                    Clock.schedule_once(lambda dt: self.log("发送成功"), 0)
                    app_logger.info("发送成功")
                    
                except Exception as e:
                    app_logger.error(f"发送失败：{e}")
                    Clock.schedule_once(lambda dt: self.log(f"失败：{e}"), 0)
                finally:
                    Clock.schedule_once(lambda dt: setattr(self, 'is_processing', False), 0)
                    self.audio_buffer.clear()
            
            asyncio.run(_send())
        
        thread = threading.Thread(target=do_send, daemon=True)
        thread.start()

    def disconnect(self):
        """断开连接"""
        app_logger.info("断开连接...")
        
        self.is_connected = False
        self.status_text = "未连接"
        self.status_label.text = "未连接"
        self.status_label.color = (0.5, 0.5, 0.5, 1)
        self.connect_btn.text = "连接服务器"
        self.connect_btn.background_color = (0.2, 0.6, 1, 1)
        self.response_text = "点击连接服务器开始使用"
        self.record_btn.disabled = True
        self.record_btn.text = "按住说话"
        self.record_btn.background_color = (0.3, 0.3, 0.3, 1)
        self.log("已断开")
        
        # 停止录音
        self.is_recording = False
        if self.audio_stream:
            try:
                self.audio_stream.stop_stream()
                self.audio_stream.close()
            except:
                pass
        
        # 关闭 WebSocket
        def close_ws():
            import asyncio
            
            async def _close():
                with self.ws_lock:
                    if self.ws and not self.ws.closed:
                        await self.ws.close()
                    if self.session:
                        await self.session.close()
            
            try:
                asyncio.run(_close())
            except:
                pass
        
        thread = threading.Thread(target=close_ws, daemon=True)
        thread.start()


class ToyPhoneApp(App):
    def build(self):
        self.title = "儿童智能语音玩具 (稳定版)"
        app_logger.info("APP 启动")
        return ToyPhoneUI()

    def on_stop(self):
        app_logger.info("APP 停止")


if __name__ == '__main__':
    ToyPhoneApp().run()
