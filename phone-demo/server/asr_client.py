"""
优化的语音识别客户端
改进:
1. 音频预处理（降噪、增益）
2. 更智能的 VAD 参数
3. 识别结果后处理
4. 错误恢复机制
"""
import os
import logging
import numpy as np
from typing import Optional

logger = logging.getLogger("asr_client")


class OptimizedASRClient:
    """优化的语音识别客户端"""
    
    def __init__(self, model_path: str = None):
        self.model = None
        self.model_path = model_path or os.path.join(
            os.path.dirname(__file__), 'models', 'whisper-tiny'
        )
        
        # VAD 参数优化
        self.vad_threshold = 0.6  # 提高阈值，减少误识别
        self.vad_min_silence = 300  # 降低静音时长，更快响应
        self.vad_min_speech = 100  # 最小语音时长
        
        # 识别参数
        self.language = "zh"
        self.task = "transcribe"  # 或 "translate"
        
        # 加载模型
        self._load_model()
    
    def _load_model(self):
        """加载 Whisper 模型"""
        try:
            from faster_whisper import WhisperModel
            
            if not os.path.exists(self.model_path):
                logger.error(f"模型不存在：{self.model_path}")
                logger.error("请先运行：python download_whisper_model.py")
                return
            
            # 使用更优的配置
            self.model = WhisperModel(
                self.model_path,
                device="cpu",
                compute_type="int8",
                cpu_threads=4  # 增加 CPU 线程数
            )
            logger.info("Whisper 模型加载成功")
            
        except Exception as e:
            logger.error(f"模型加载失败：{e}")
            self.model = None
    
    def _preprocess_audio(self, audio_data: bytes) -> np.ndarray:
        """
        音频预处理
        
        Args:
            audio_data: PCM 音频数据 (16kHz, 16bit, 单声道)
        
        Returns:
            归一化的 float32 数组
        """
        try:
            # 转换为 numpy 数组
            audio_array = np.frombuffer(audio_data, dtype=np.int16)
            
            # 检查音频是否为空
            if len(audio_array) == 0:
                logger.warning("音频数据为空")
                return np.array([], dtype=np.float32)
            
            # 归一化到 [-1, 1]
            audio_float = audio_array.astype(np.float32) / 32768.0
            
            # 降噪：去除直流分量
            audio_float = audio_float - np.mean(audio_float)
            
            # 增益控制：标准化音量
            max_amp = np.max(np.abs(audio_float))
            if max_amp > 0 and max_amp < 0.5:  # 音量太小，放大
                gain = 0.5 / max_amp
                audio_float = audio_float * gain
                logger.debug(f"应用增益：{gain:.2f}")
            
            # 限制幅度，防止削波
            audio_float = np.clip(audio_float, -0.95, 0.95)
            
            return audio_float
            
        except Exception as e:
            logger.error(f"音频预处理失败：{e}")
            return np.array([], dtype=np.float32)
    
    def _detect_speech(self, audio_array: np.ndarray) -> bool:
        """
        简单的语音活动检测
        
        Args:
            audio_array: 音频数组
        
        Returns:
            是否检测到语音
        """
        if len(audio_array) == 0:
            return False
        
        # 计算能量
        energy = np.mean(audio_array ** 2)
        
        # 简单能量阈值检测
        energy_threshold = 0.001  # 能量阈值
        has_speech = energy > energy_threshold
        
        if has_speech:
            logger.debug(f"检测到语音，能量：{energy:.6f}")
        else:
            logger.debug(f"未检测到语音，能量：{energy:.6f}")
        
        return has_speech
    
    def transcribe(self, audio_data: bytes) -> str:
        """
        语音识别
        
        Args:
            audio_data: PCM 音频数据 (16kHz, 16bit, 单声道)
        
        Returns:
            识别的文本
        """
        if self.model is None:
            logger.error("模型未加载")
            return ""
        
        try:
            # 1. 音频预处理
            audio_array = self._preprocess_audio(audio_data)
            
            if len(audio_array) == 0:
                logger.warning("预处理后音频为空")
                return ""
            
            # 2. 检查音频长度
            duration = len(audio_array) / 16000  # 16kHz 采样率
            logger.info(f"音频时长：{duration:.2f}秒")
            
            if duration < 0.3:  # 小于 0.3 秒，跳过
                logger.warning("音频太短，跳过识别")
                return ""
            
            if duration > 30:  # 大于 30 秒，截断
                logger.warning("音频太长，截断到 30 秒")
                audio_array = audio_array[:16000 * 30]
            
            # 3. 语音活动检测
            if not self._detect_speech(audio_array):
                logger.info("未检测到有效语音")
                return ""
            
            # 4. Whisper 识别
            segments, info = self.model.transcribe(
                audio_array,
                language=self.language,
                task=self.task,
                vad_filter=True,
                vad_parameters=dict(
                    threshold=self.vad_threshold,
                    min_silence_duration_ms=self.vad_min_silence,
                    min_speech_duration_ms=self.vad_min_speech
                ),
                beam_size=5,  # 束搜索宽度
                best_of=3,    # 最佳候选数
                temperature=0.0,  # 贪婪解码
                compression_ratio_threshold=2.5,  # 压缩率阈值
                log_prob_threshold=-1.0,  # 对数概率阈值
                no_speech_threshold=0.6   # 无语音阈值
            )
            
            # 5. 收集识别结果
            text_parts = []
            for segment in segments:
                text = segment.text.strip()
                if text:
                    text_parts.append(text)
                    logger.debug(f"识别片段：{text}")
            
            # 6. 合并结果
            text = " ".join(text_parts)
            
            # 7. 后处理
            text = self._postprocess_text(text)
            
            if text:
                logger.info(f"[ASR] ✅ 识别结果：{text}")
            else:
                logger.warning("[ASR] 未识别到有效内容")
            
            return text
            
        except Exception as e:
            logger.error(f"语音识别失败：{e}", exc_info=True)
            return ""
    
    def _postprocess_text(self, text: str) -> str:
        """
        文本后处理
        
        Args:
            text: 识别的原始文本
        
        Returns:
            处理后的文本
        """
        if not text:
            return ""
        
        # 去除首尾空格
        text = text.strip()
        
        # 去除特殊字符
        import re
        text = re.sub(r'[^\w\s，。！？、；：""''（）【】《》\.\,\!\?\;]', '', text)
        
        # 去除连续的标点符号
        text = re.sub(r'[，。！？]{2,}', lambda m: m.group(0)[0], text)
        
        # 去除无意义的词
        meaningless = ['嗯', '啊', '呃', '哦', '哎', '嘛', '啦']
        for word in meaningless:
            text = text.replace(word, '')
        
        # 再次清理空格
        text = ' '.join(text.split())
        
        return text


# 全局实例
_asr_instance: Optional[OptimizedASRClient] = None


def get_asr_client() -> OptimizedASRClient:
    """获取 ASR 客户端实例"""
    global _asr_instance
    if _asr_instance is None:
        _asr_instance = OptimizedASRClient()
    return _asr_instance
