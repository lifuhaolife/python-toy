# 语音识别引擎使用说明

## 概述

本项目支持三种语音识别引擎，按推荐程度排序：

| 引擎 | 推荐度 | 准确率 | 速度 | 安装 |
|------|--------|--------|------|------|
| **Sherpa-ONNX** | ⭐⭐⭐⭐⭐ | 80-85% | 最快 (0.2-0.5s) | 已安装 |
| **FunASR** | ⭐⭐⭐⭐ | 85-90% | 快 (0.5-1s) | 需额外安装 |
| **Whisper** | ⭐⭐⭐ | 60-70% | 慢 (2-3s) | 已安装 |

## 快速开始

### 使用 Sherpa-ONNX（推荐）

```cmd
# 设置环境变量
set ASR_ENGINE=sherpa

# 启动服务器
cd phone-demo/server
python server.py
```

**首次运行**会自动下载模型（约 50MB，下载到 `~/.cache/sherpa-onnx`）。

### 使用 FunASR（中文最优）

```cmd
# 设置环境变量
set ASR_ENGINE=funasr

# 启动服务器
cd phone-demo/server
python server.py
```

**需要安装依赖:**
```bash
conda install -c conda-forge funasr
```

### 使用 Whisper（备用）

```cmd
# 设置环境变量
set ASR_ENGINE=whisper

# 启动服务器
cd phone-demo/server
python server.py
```

## 测试

### 测试 Sherpa-ONNX
```bash
python test_sherpa.py
```

### 测试 FunASR
```bash
python test_funasr.py
```

### 测试 Whisper
```bash
python test_asr.py
```

## 引擎对比

### Sherpa-ONNX
**优点:**
- ✅ 识别速度最快（0.2-0.5 秒/2 秒音频）
- ✅ 模型小（约 50MB）
- ✅ 完全离线
- ✅ 支持流式识别
- ✅ 已安装，无需额外依赖

**缺点:**
- ⚠️ 首次运行需要下载模型
- ⚠️ 中文准确率略低于 FunASR

**适用场景:** 实时语音识别、对速度要求高的场景

### FunASR Paraformer
**优点:**
- ✅ 中文识别率最高（85-90%）
- ✅ 内置 VAD 和标点模型
- ✅ 自动繁简转换

**缺点:**
- ⚠️ 依赖多，安装复杂
- ⚠️ 模型大（约 200MB）
- ⚠️ 识别速度慢于 Sherpa-ONNX

**适用场景:** 对准确率要求高的中文识别

### Whisper
**优点:**
- ✅ 支持 99+ 种语言
- ✅ 已安装
- ✅ 稳定可靠

**缺点:**
- ❌ 识别速度慢（2-3 秒/2 秒音频）
- ❌ 中文准确率较低（60-70%）
- ❌ 无标点符号

**适用场景:** 多语言识别、备用方案

## 代码示例

### 基本使用
```python
from asr_client import get_asr_client

# 获取 ASR 客户端（自动选择配置的引擎）
asr = get_asr_client()

# 识别音频
audio_data = b'...'  # PCM 音频 (16kHz, 16bit, 单声道)
text = asr.transcribe(audio_data)

print(f"识别结果：{text}")
```

### 直接使用 Sherpa-ONNX
```python
from asr_sherpa import get_sherpa_client

asr = get_sherpa_client()
text = asr.transcribe(audio_data)
```

### 直接使用 FunASR
```python
from asr_funasr import get_funasr_client

asr = get_funasr_client(model_name="paraformer-zh")
text = asr.transcribe(audio_data)
```

## 故障排查

### 问题 1: Sherpa-ONNX 模型下载失败

**错误:** `No graph was found in the protobuf`

**解决:**
```bash
# 手动下载模型
pip install -U sherpa-onnx

# 或检查网络连接
```

### 问题 2: FunASR 依赖缺失

**错误:** `No module named 'xxx'`

**解决:**
```bash
# 使用 conda 安装
conda install -c conda-forge funasr

# 或手动安装依赖
pip install omegaconf torch_complex kaldiio soundfile resampy librosa
```

### 问题 3: 识别结果为空

**可能原因:**
1. 音频音量太小
2. 音频时长太短 (< 0.3 秒)
3. VAD 阈值太高

**解决:**
- 检查音频质量
- 调整 VAD 参数
- 使用更敏感的引擎（Sherpa-ONNX）

## 总结

**推荐配置:**
- **首选**: Sherpa-ONNX（速度快，已安装）
- **中文优化**: FunASR（准确率高）
- **备用**: Whisper（多语言）

**设置方法:**
```cmd
set ASR_ENGINE=sherpa    # 或 funasr 或 whisper
```
