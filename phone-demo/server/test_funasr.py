"""
FunASR 语音识别测试脚本
测试阿里达摩院 Paraformer 中文识别效果
"""
import os
import sys
import wave
import tempfile
import numpy as np

# 添加路径
sys.path.insert(0, os.path.dirname(__file__))

from asr_funasr import FunASRClient, get_funasr_client


def generate_test_audio(filename: str = "test_audio.wav", duration: float = 2.0, frequency: float = 440):
    """生成测试音频文件"""
    sample_rate = 16000
    samples = int(duration * sample_rate)
    
    # 生成正弦波
    t = np.linspace(0, duration, samples, dtype=np.float32)
    audio_data = (np.sin(2 * np.pi * frequency * t) * 32767 * 0.5).astype(np.int16)
    
    # 保存为 WAV 文件
    with wave.open(filename, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(audio_data.tobytes())
    
    print(f"测试音频已生成：{filename}")
    print(f"  时长：{duration}秒，频率：{frequency}Hz")
    return filename


def load_audio(filename: str) -> bytes:
    """加载音频文件"""
    with wave.open(filename, 'rb') as wf:
        assert wf.getnchannels() == 1, "必须是单声道"
        assert wf.getsampwidth() == 2, "必须是 16bit"
        assert wf.getframerate() == 16000, "必须是 16kHz"
        return wf.readframes(wf.getnframes())


def test_funasr():
    """测试 FunASR 识别"""
    print("=" * 60)
    print("FunASR 语音识别测试")
    print("=" * 60)
    
    # 1. 创建客户端
    print("\n[1] 初始化 FunASR 客户端...")
    asr = get_funasr_client(model_name="paraformer-zh")
    
    if not asr.initialized:
        print("X 模型未初始化，请确保已安装 FunASR")
        print("  运行：conda install -c conda-forge funasr")
        return False
    
    print("OK FunASR 客户端已就绪")
    
    # 2. 生成测试音频
    print("\n[2] 生成测试音频...")
    audio_file = generate_test_audio(duration=2.0, frequency=440)
    
    # 3. 加载音频
    print("\n[3] 加载音频文件...")
    audio_data = load_audio(audio_file)
    print(f"OK 音频数据：{len(audio_data)} 字节")
    
    # 4. 测试识别
    print("\n[4] 测试语音识别...")
    result = asr.transcribe(audio_data)
    
    print(f"\n识别结果：'{result}'")
    print("说明：440Hz 正弦波不是人声，识别为空是正常的")
    
    # 5. 清理
    if os.path.exists(audio_file):
        os.remove(audio_file)
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
    
    return True


def test_model_info():
    """显示模型信息"""
    print("\n" + "=" * 60)
    print("FunASR 模型信息")
    print("=" * 60)
    
    print("\n可用模型:")
    print("  - paraformer-zh: 中文识别（推荐）")
    print("  - paraformer-en: 英文识别")
    print("  - paraformer-zh-en: 中英混合")
    
    print("\n特点:")
    print("  - 中文识别率：85-90%")
    print("  - 识别速度：0.5-1 秒/2 秒音频")
    print("  - 内置 VAD 和标点模型")
    print("  - 完全离线运行")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    test_model_info()
    test_funasr()
