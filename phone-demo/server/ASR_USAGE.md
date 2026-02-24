# 语音识别优化方案

## 概述

本项目支持两种语音识别引擎：
1. **FunASR Paraformer**（推荐）：阿里达摩院出品，中文识别率 85-90%
2. **Whisper**（备用）：OpenAI 出品，多语言支持

## 方案对比

| 特性 | FunASR Paraformer | Whisper Tiny |
|------|------------------|--------------|
| 中文准确率 | 85-90% | 60-70% |
| 识别速度 | 0.5-1 秒/2 秒音频 | 2-3 秒/2 秒音频 |
| 模型大小 | ~200MB | ~39MB |
| 标点符号 | ✅ 自动添加 | ❌ 需后处理 |
| VAD | ✅ 内置高质量 | ⚠️ 基础 |
| 多语言 | 中文为主 | 支持 99+ 语言 |

## 安装

### 方案 1: FunASR（推荐）

```bash
# 使用 conda 安装（推荐，避免编译问题）
conda install -c conda-forge funasr

# 或使用 pip 安装（需要 Visual C++ Build Tools）
pip install funasr modelscope torch omegaconf torch_complex kaldiio soundfile resampy librosa
```

### 方案 2: Whisper（已安装）

Whisper 已经安装，无需额外操作。

### 方案 3: Sherpa-ONNX（最快，已安装）

Sherpa-ONNX 已安装，支持流式识别，速度最快。

```bash
pip install sherpa-onnx  # 已完成
```

## 使用

### 设置 ASR 引擎

**Windows:**
```cmd
set ASR_ENGINE=funasr
```

**Linux/Mac:**
```bash
export ASR_ENGINE=funasr
```

**可用值:**
- `funasr` - FunASR Paraformer（推荐）
- `whisper` - Whisper

### 启动服务器

```bash
cd phone-demo/server
python server.py
```

### 测试

**测试 FunASR:**
```bash
python test_funasr.py
```

**测试 Whisper:**
```bash
python test_asr.py
```

## 代码示例

### 使用 ASR 客户端

```python
from asr_client import get_asr_client

# 获取 ASR 客户端（自动选择引擎）
asr = get_asr_client()

# 识别音频
audio_data = b'...'  # PCM 音频 (16kHz, 16bit, 单声道)
text = asr.transcribe(audio_data)

print(f"识别结果：{text}")
```

### 直接使用 FunASR

```python
from asr_funasr import FunASRClient

asr = FunASRClient(model_name="paraformer-zh")
text = asr.transcribe(audio_data)
```

### 直接使用 Whisper

```python
from asr_whisper import OptimizedASRClient

asr = OptimizedASRClient()
text = asr.transcribe(audio_data)
```

## 性能优化

### 1. 使用 GPU（可选）

如果有 NVIDIA GPU：

```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

FunASR 会自动使用 GPU 加速。

### 2. 调整 VAD 参数

在 `asr_whisper.py` 中调整：

```python
self.vad_threshold = 0.45  # 降低阈值，更敏感
self.vad_min_speech = 250  # 增加最小语音时长
```

### 3. 使用流式识别（Sherpa-ONNX）

创建 `asr_sherpa.py` 使用 Sherpa-ONNX 实现真正的流式识别。

## 故障排查

### 问题 1: FunASR 加载失败

**错误:** `No module named 'xxx'`

**解决:**
```bash
# 安装缺失的依赖
pip install <missing-module>

# 或使用 conda 重新安装
conda install -c conda-forge funasr
```

### 问题 2: 识别结果为空

**可能原因:**
1. 音频音量太小
2. 音频时长太短 (< 0.3 秒)
3. VAD 阈值太高

**解决:**
```python
# 降低 VAD 阈值
asr.vad_threshold = 0.4  # 默认 0.6

# 检查音频预处理
audio_array = asr._preprocess_audio(audio_data)
print(f"音频能量：{np.mean(audio_array ** 2)}")
```

### 问题 3: 识别速度慢

**解决:**
1. 使用 GPU
2. 减小模型：`model_name="paraformer-zh-small"`
3. 使用 Sherpa-ONNX（最快）

## 总结

**推荐配置:**
- **引擎**: FunASR Paraformer
- **模型**: paraformer-zh
- **环境**: Conda
- **设备**: CPU 即可（GPU 更快）

**预期效果:**
- 中文识别率：85-90%
- 识别速度：0.5-1 秒/2 秒音频
- 自动添加标点
- 自动繁简转换
