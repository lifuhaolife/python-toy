"""
Whisper 语音识别客户端（备用方案）
"""
import os
import logging
import numpy as np
from typing import Optional

logger = logging.getLogger("asr_whisper")


class OptimizedASRClient:
    """优化的 Whisper 语音识别客户端"""

    def __init__(self, model_path: str = None):
        self.model = None
        self.model_path = model_path or os.path.join(
            os.path.dirname(__file__), 'models', 'whisper-tiny'
        )

        # VAD 参数优化
        self.vad_threshold = 0.6
        self.vad_min_silence = 300
        self.vad_min_speech = 100

        # 识别参数
        self.language = "zh"
        self.task = "transcribe"

        # 加载模型
        self._load_model()

    def _load_model(self):
        """加载 Whisper 模型"""
        try:
            from faster_whisper import WhisperModel

            if not os.path.exists(self.model_path):
                logger.error(f"模型不存在：{self.model_path}")
                return

            self.model = WhisperModel(
                self.model_path,
                device="cpu",
                compute_type="int8",
                cpu_threads=4
            )
            logger.info("Whisper 模型加载成功")

        except Exception as e:
            logger.error(f"模型加载失败：{e}")
            self.model = None

    def _preprocess_audio(self, audio_data: bytes) -> np.ndarray:
        """音频预处理"""
        try:
            audio_array = np.frombuffer(audio_data, dtype=np.int16)
            if len(audio_array) == 0:
                return np.array([], dtype=np.float32)

            audio_float = audio_array.astype(np.float32) / 32768.0
            audio_float = audio_float - np.mean(audio_float)
            
            max_amp = np.max(np.abs(audio_float))
            if max_amp > 0 and max_amp < 0.5:
                gain = 0.5 / max_amp
                audio_float = audio_float * gain

            audio_float = np.clip(audio_float, -0.95, 0.95)
            return audio_float

        except Exception as e:
            logger.error(f"音频预处理失败：{e}")
            return np.array([], dtype=np.float32)

    def _detect_speech(self, audio_array: np.ndarray) -> bool:
        """简单的语音活动检测"""
        if len(audio_array) == 0:
            return False
        energy = np.mean(audio_array ** 2)
        return energy > 0.001

    def transcribe(self, audio_data: bytes) -> str:
        """语音识别"""
        if self.model is None:
            return ""

        try:
            audio_array = self._preprocess_audio(audio_data)
            if len(audio_array) == 0:
                return ""

            duration = len(audio_array) / 16000
            if duration < 0.3:
                return ""
            if duration > 30:
                audio_array = audio_array[:16000 * 30]

            if not self._detect_speech(audio_array):
                return ""

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
                beam_size=5,
                best_of=5,
                temperature=0.0,
                length_penalty=1.0,
                repetition_penalty=1.0,
                no_repeat_ngram_size=3,
                compression_ratio_threshold=2.5,
                log_prob_threshold=-1.0,
                no_speech_threshold=0.6,
            )

            text = " ".join([s.text.strip() for s in segments if s.text.strip()])
            text = self._postprocess_text(text)

            return text

        except Exception as e:
            logger.error(f"语音识别失败：{e}")
            return ""

    def _postprocess_text(self, text: str) -> str:
        """文本后处理"""
        if not text:
            return ""

        # 繁体转简体
        text = self._traditional_to_simplified(text)
        text = text.strip()

        # 去除特殊字符
        import re
        text = re.sub(r'[^\w\s，。！？、；：""''（）【】《》\.\,\!\?\;]', '', text)
        text = re.sub(r'[，。！？]{2,}', lambda m: m.group(0)[0], text)

        # 去除无意义词
        for word in ['嗯', '啊', '呃', '哦', '哎', '嘛', '啦']:
            text = text.replace(word, '')

        return ' '.join(text.split())

    def _traditional_to_simplified(self, text: str) -> str:
        """繁体转简体"""
        mapping = {
            '麼': '么', '為': '为', '們': '们', '個': '个', '這': '这',
            '樣': '样', '說': '说', '話': '话', '時': '时', '間': '间',
            '會': '会', '現': '现', '來': '来', '點': '点', '兒': '儿',
            '讓': '让', '請': '请', '問': '问', '覺': '觉', '歡': '欢',
            '迎': '迎', '謝': '谢', '對': '对', '於': '于', '沒': '没',
            '邊': '边', '裏': '里', '嗎': '吗', '著': '着', '過': '过',
            '還': '还', '經': '经', '證': '证', '東': '东',
        }
        return ''.join([mapping.get(c, c) for c in text])


# 全局实例
_asr_instance: Optional[OptimizedASRClient] = None


def get_whisper_client() -> OptimizedASRClient:
    """获取 Whisper ASR 客户端实例"""
    global _asr_instance
    if _asr_instance is None:
        _asr_instance = OptimizedASRClient()
    return _asr_instance
