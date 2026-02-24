"""
ASR 语音识别测试脚本
测试 Whisper 识别效果
"""
import os
import sys
import wave
import numpy as np

# 添加路径
sys.path.insert(0, os.path.dirname(__file__))

from asr_client import OptimizedASRClient, get_asr_client


def generate_test_audio(filename: str = "test_audio.wav", duration: float = 2.0, frequency: float = 440):
    """生成测试音频文件"""
    sample_rate = 16000
    samples = int(duration * sample_rate)
    
    # 生成正弦波
    t = np.linspace(0, duration, samples, dtype=np.float32)
    audio_data = (np.sin(2 * np.pi * frequency * t) * 32767 * 0.5).astype(np.int16)
    
    # 保存为 WAV 文件
    with wave.open(filename, 'wb') as wf:
        wf.setnchannels(1)  # 单声道
        wf.setsampwidth(2)  # 16bit
        wf.setframerate(sample_rate)
        wf.writeframes(audio_data.tobytes())
    
    print(f"✅ 测试音频已生成：{filename}")
    print(f"   时长：{duration}秒，频率：{frequency}Hz")
    return filename


def load_audio(filename: str) -> bytes:
    """加载音频文件"""
    with wave.open(filename, 'rb') as wf:
        # 验证格式
        assert wf.getnchannels() == 1, "必须是单声道"
        assert wf.getsampwidth() == 2, "必须是 16bit"
        assert wf.getframerate() == 16000, "必须是 16kHz"
        
        # 读取数据
        audio_data = wf.readframes(wf.getnframes())
        return audio_data


def test_asr():
    """测试 ASR 识别"""
    print("=" * 60)
    print("ASR 语音识别测试")
    print("=" * 60)
    
    # 1. 创建 ASR 客户端
    print("\n[1] 初始化 ASR 客户端...")
    asr = get_asr_client()
    
    if asr.model is None:
        print("❌ 模型未加载，请确保已下载 Whisper 模型")
        print("   运行：python download_whisper_model.py")
        return False
    
    print("✅ ASR 客户端已就绪")
    
    # 2. 生成测试音频
    print("\n[2] 生成测试音频...")
    audio_file = generate_test_audio(duration=2.0, frequency=440)
    
    # 3. 加载音频
    print("\n[3] 加载音频文件...")
    audio_data = load_audio(audio_file)
    print(f"✅ 音频数据：{len(audio_data)} 字节")
    
    # 4. 测试识别
    print("\n[4] 测试语音识别...")
    result = asr.transcribe(audio_data)
    
    print(f"\n识别结果：'{result}'")
    
    # 5. 清理
    if os.path.exists(audio_file):
        os.remove(audio_file)
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
    
    return True


def test_audio_preprocessing():
    """测试音频预处理"""
    print("\n" + "=" * 60)
    print("音频预处理测试")
    print("=" * 60)
    
    asr = get_asr_client()
    
    # 生成不同音量的测试音频
    sample_rate = 16000
    duration = 2.0
    samples = int(duration * sample_rate)
    t = np.linspace(0, duration, samples, dtype=np.float32)
    
    test_cases = [
        ("正常音量", 0.5),
        ("小音量", 0.1),
        ("大音量", 0.9),
    ]
    
    for name, amplitude in test_cases:
        print(f"\n测试：{name} (振幅：{amplitude})")
        
        # 生成音频
        audio_data = (np.sin(2 * np.pi * 440 * t) * 32767 * amplitude).astype(np.int16)
        
        # 预处理
        processed = asr._preprocess_audio(audio_data.tobytes())
        
        # 统计
        print(f"  原始范围：[{audio_data.min()}, {audio_data.max()}]")
        print(f"  处理后范围：[{processed.min():.4f}, {processed.max():.4f}]")
        print(f"  处理后能量：{np.mean(processed ** 2):.6f}")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    # 测试预处理
    test_audio_preprocessing()
    
    # 测试识别
    test_asr()
