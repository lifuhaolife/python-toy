"""
手动下载 Whisper 模型脚本
用于在国内网络环境下下载 Whisper 模型

使用方法:
1. 使用代理运行此脚本
2. 或从镜像站下载模型文件
"""
import os
import sys

# 模型路径
MODEL_DIR = os.path.join(os.path.dirname(__file__), 'models', 'whisper-tiny')
os.makedirs(MODEL_DIR, exist_ok=True)

print("=" * 60)
print("Whisper 模型下载工具")
print("=" * 60)
print()
print(f"模型保存路径：{MODEL_DIR}")
print()

# 方法 1: 使用 huggingface 镜像
print("方法 1: 使用镜像站下载（推荐）")
print("-" * 60)
print("设置环境变量使用镜像:")
print('  set HF_ENDPOINT=https://hf-mirror.com')
print()
print("然后运行:")
print('  python -c "from faster_whisper import WhisperModel; WhisperModel(\'tiny\', download_root=\'' + MODEL_DIR + '\')"')
print()

# 方法 2: 手动下载
print("方法 2: 手动下载模型文件")
print("-" * 60)
print("1. 访问以下地址下载模型:")
print("   https://huggingface.co/guillaumekln/faster-whisper-tiny")
print()
print("2. 或使用 git clone:")
print("   git lfs install")
print("   git clone https://huggingface.co/guillaumekln/faster-whisper-tiny")
print()

# 方法 3: 使用模拟模式
print("方法 3: 使用模拟模式（无需下载）")
print("-" * 60)
print("如果无法下载，服务器会自动使用模拟识别模式")
print("随机返回预设的常用语，不影响测试流程")
print()

print("=" * 60)
print()

# 尝试下载
try:
    response = input("是否尝试下载模型？(y/n): ").strip().lower()
    
    if response == 'y':
        print()
        print("正在设置镜像地址...")
        os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
        
        print("正在下载模型（约 2 分钟，请耐心等待）...")
        from faster_whisper import WhisperModel
        
        model = WhisperModel(
            "tiny",
            device="cpu",
            compute_type="int8",
            download_root=MODEL_DIR
        )
        
        print()
        print("=" * 60)
        print("✅ 模型下载成功!")
        print(f"模型路径：{MODEL_DIR}")
        print("=" * 60)
        
    else:
        print()
        print("已取消下载，将使用模拟识别模式")
        
except Exception as e:
    print()
    print("=" * 60)
    print(f"❌ 下载失败：{e}")
    print("=" * 60)
    print()
    print("将使用模拟识别模式，不影响基本功能")
    print()
    print("如需真实语音识别，请:")
    print("1. 使用代理后重新运行此脚本")
    print("2. 或手动从镜像站下载模型文件")

print()
input("按回车键退出...")
