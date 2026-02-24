"""
Sherpa-ONNX 语音识别客户端（简洁版）
"""
import os
import logging
import numpy as np
from typing import Optional

logger = logging.getLogger("asr_sherpa")


class SherpaASRClient:
    """Sherpa-ONNX 语音识别客户端"""

    def __init__(self):
        self.recognizer = None
        self.initialized = False
        self._init_model()

    def _init_model(self):
        """初始化模型"""
        try:
            import sherpa_onnx

            # 使用预训练模型（首次自动下载）
            self.recognizer = sherpa_onnx.OfflineRecognizer.from_pretrained(
                model_name="sherpa-onnx-paraformer-zh-2024-03-06",
                num_threads=4,
                sample_rate=16000,
                feature_dim=80,
                decoding_method="greedy",
            )
            self.initialized = True
            logger.info("✅ Sherpa-ONNX 模型已加载")
        except Exception as e:
            logger.error(f"Sherpa-ONNX 加载失败：{e}")
            self.initialized = False

    def transcribe(self, audio_data: bytes, sample_rate: int = 16000) -> str:
        """语音识别"""
        if not self.initialized:
            return ""

        try:
            import sherpa_onnx

            # 转换为 numpy 数组
            audio_array = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0

            # 检查长度
            duration = len(audio_array) / sample_rate
            if duration < 0.3 or duration > 60:
                return ""

            # 创建流并识别
            stream = self.recognizer.create_stream()
            stream.accept_waveform(sample_rate, audio_array)
            self.recognizer.decode_stream(stream)

            text = stream.result.text
            return self._postprocess(text) if text else ""

        except Exception as e:
            logger.error(f"识别失败：{e}")
            return ""

    def _postprocess(self, text: str) -> str:
        """后处理"""
        # 繁简转换
        mapping = {
            '麼': '么', '為': '为', '們': '们', '個': '个', '這': '这',
            '樣': '样', '說': '说', '話': '话', '時': '时', '間': '间',
            '會': '会', '來': '来', '點': '点', '兒': '儿', '嗎': '吗',
            '著': '着', '過': '过', '還': '还', '經': '经',
        }
        text = ''.join([mapping.get(c, c) for c in text])

        # 清理
        import re
        text = re.sub(r'[^\w\s，。！？、；：""（）【】《》.,!?;]', '', text)
        text = re.sub(r'[，。！？]{2,}', lambda m: m.group(0)[0], text)
        for word in ['嗯', '啊', '呃', '哦', '哎', '嘛', '啦']:
            text = text.replace(word, '')

        return ' '.join(text.split())


_sherpa_instance: Optional[SherpaASRClient] = None


def get_sherpa_client() -> SherpaASRClient:
    """获取 Sherpa 客户端"""
    global _sherpa_instance
    if _sherpa_instance is None:
        _sherpa_instance = SherpaASRClient()
    return _sherpa_instance
