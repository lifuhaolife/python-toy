"""
FunASR Paraformer 语音识别客户端
阿里达摩院出品，专为中文优化的离线语音识别模型

特点:
1. 中文识别准确率 85-90%
2. CPU 上 0.5-1 秒处理 2 秒音频
3. 内置 VAD 和标点模型
4. 完全离线运行

安装:
    conda install -c conda-forge funasr

使用:
    from asr_funasr import FunASRClient
    asr = FunASRClient()
    text = asr.transcribe(audio_data)
"""
import os
import logging
import tempfile
import wave
from typing import Optional

logger = logging.getLogger("asr_funasr")


class FunASRClient:
    """FunASR Paraformer 语音识别客户端"""
    
    def __init__(self, model_name: str = "paraformer-zh"):
        """
        初始化 FunASR 客户端
        
        Args:
            model_name: 模型名称
                - paraformer-zh: 中文识别（推荐）
                - paraformer-en: 英文识别
                - paraformer-zh-en: 中英混合
        """
        self.model_name = model_name
        self.model = None
        self.initialized = False
        
        # 模型配置
        self.model_config = {
            "model": model_name,
            "vad_model": "fsmn-vad",      # VAD 模型
            "punc_model": "ct-punc",      # 标点模型
            "device": "cpu"
        }
        
        logger.info(f"FunASR 客户端初始化：{model_name}")
        
        # 懒加载模型
        self._lazy_init()
    
    def _lazy_init(self):
        """懒加载模型（首次调用时加载）"""
        try:
            from funasr import AutoModel
            
            logger.info("正在加载 FunASR 模型...")
            
            # 加载模型
            self.model = AutoModel(**self.model_config)
            
            self.initialized = True
            logger.info(f"✅ FunASR 模型加载成功：{self.model_name}")
            
        except Exception as e:
            logger.error(f"❌ FunASR 模型加载失败：{e}")
            self.initialized = False
    
    def _audio_bytes_to_wav(self, audio_data: bytes, sample_rate: int = 16000) -> str:
        """
        将 PCM 音频字节转换为 WAV 文件
        
        Args:
            audio_data: PCM 音频数据 (16kHz, 16bit, 单声道)
            sample_rate: 采样率
        
        Returns:
            临时 WAV 文件路径
        """
        # 创建临时文件
        temp_file = tempfile.mktemp(suffix='.wav')
        
        try:
            # 写入 WAV 文件
            with wave.open(temp_file, 'wb') as wf:
                wf.setnchannels(1)  # 单声道
                wf.setsampwidth(2)  # 16bit
                wf.setframerate(sample_rate)
                wf.writeframes(audio_data)
            
            return temp_file
            
        except Exception as e:
            logger.error(f"音频转换失败：{e}")
            if os.path.exists(temp_file):
                os.remove(temp_file)
            return None
    
    def transcribe(self, audio_data: bytes, language: str = "zh") -> str:
        """
        语音识别
        
        Args:
            audio_data: PCM 音频数据 (16kHz, 16bit, 单声道)
            language: 语言 (zh/en)
        
        Returns:
            识别的文本
        """
        if not self.initialized:
            logger.error("模型未初始化")
            return ""
        
        try:
            # 1. 检查音频数据
            if len(audio_data) == 0:
                logger.warning("音频数据为空")
                return ""
            
            # 2. 检查音频时长
            duration = len(audio_data) / (16000 * 2)  # 16kHz, 16bit
            logger.info(f"音频时长：{duration:.2f}秒")
            
            if duration < 0.3:
                logger.warning("音频太短，跳过识别")
                return ""
            
            if duration > 60:
                logger.warning("音频太长，截断到 60 秒")
                audio_data = audio_data[:60 * 16000 * 2]
            
            # 3. 转换为 WAV 文件
            wav_file = self._audio_bytes_to_wav(audio_data)
            if not wav_file:
                return ""
            
            try:
                # 4. 使用 FunASR 识别
                result = self.model.generate(input=wav_file)
                
                # 5. 提取文本
                if result and len(result) > 0:
                    text = result[0].get("text", "")
                    
                    if text:
                        logger.info(f"[ASR] ✅ 识别结果：{text}")
                    else:
                        logger.warning("[ASR] 未识别到有效内容")
                    
                    return text
                else:
                    logger.warning("[ASR] 识别结果为空")
                    return ""
                    
            finally:
                # 6. 清理临时文件
                if os.path.exists(wav_file):
                    os.remove(wav_file)
            
        except Exception as e:
            logger.error(f"语音识别失败：{e}", exc_info=True)
            return ""
    
    def transcribe_batch(self, audio_files: list) -> list:
        """
        批量识别
        
        Args:
            audio_files: WAV 文件路径列表
        
        Returns:
            识别结果列表
        """
        if not self.initialized:
            logger.error("模型未初始化")
            return []
        
        try:
            result = self.model.generate(input=audio_files)
            return [r.get("text", "") for r in result]
            
        except Exception as e:
            logger.error(f"批量识别失败：{e}")
            return []
    
    def close(self):
        """关闭模型，释放资源"""
        if self.model:
            del self.model
            self.model = None
            self.initialized = False
            logger.info("FunASR 模型已关闭")


# 全局实例
_funasr_instance: Optional[FunASRClient] = None


def get_funasr_client(model_name: str = "paraformer-zh") -> FunASRClient:
    """
    获取 FunASR 客户端实例
    
    Args:
        model_name: 模型名称
    
    Returns:
        FunASR 客户端实例
    """
    global _funasr_instance
    if _funasr_instance is None or _funasr_instance.model_name != model_name:
        _funasr_instance = FunASRClient(model_name)
    return _funasr_instance
