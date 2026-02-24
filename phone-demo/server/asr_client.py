"""
语音识别客户端（支持三引擎）
- Sherpa-ONNX（推荐）：速度快，准确率高，已安装
- FunASR Paraformer：中文优化，需要额外依赖
- Whisper（备用）：多语言支持

使用环境变量选择引擎:
    set ASR_ENGINE=sherpa    # Sherpa-ONNX（推荐）
    set ASR_ENGINE=funasr    # FunASR Paraformer
    set ASR_ENGINE=whisper   # Whisper
"""
import os
import logging
from typing import Optional

logger = logging.getLogger("asr_client")

# 从环境变量读取 ASR 引擎
ASR_ENGINE = os.getenv("ASR_ENGINE", "sherpa").lower()
logger.info(f"ASR 引擎配置：{ASR_ENGINE}")


def get_asr_client():
    """
    获取 ASR 客户端实例
    
    Returns:
        ASR 客户端实例（Sherpa-ONNX / FunASR / Whisper）
    """
    if ASR_ENGINE == "sherpa":
        # 使用 Sherpa-ONNX（推荐）
        try:
            from asr_sherpa import get_sherpa_client
            logger.info("使用 Sherpa-ONNX 引擎（速度快，已安装）")
            return get_sherpa_client(model_type="paraformer")
        except Exception as e:
            logger.error(f"Sherpa-ONNX 加载失败：{e}，回退到 FunASR")
            return _get_funasr_client()
    elif ASR_ENGINE == "funasr":
        # 使用 FunASR
        try:
            from asr_funasr import get_funasr_client
            logger.info("使用 FunASR Paraformer 引擎（中文优化）")
            return get_funasr_client(model_name="paraformer-zh")
        except Exception as e:
            logger.error(f"FunASR 加载失败：{e}，回退到 Whisper")
            return _get_whisper_client()
    else:
        # 使用 Whisper
        logger.info("使用 Whisper 引擎")
        return _get_whisper_client()


def _get_funasr_client():
    """获取 FunASR ASR 客户端"""
    from asr_funasr import get_funasr_client
    return get_funasr_client()


def _get_whisper_client():
    """获取 Whisper ASR 客户端"""
    from asr_whisper import get_whisper_client
    return get_whisper_client()


# 导出类（用于类型提示）
def __getattr__(name):
    if name == "SherpaASRClient":
        from asr_sherpa import SherpaASRClient
        return SherpaASRClient
    if name == "OptimizedASRClient":
        from asr_whisper import OptimizedASRClient
        return OptimizedASRClient
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
