# 儿童智能语音玩具 - 旧手机验证版

> 使用旧 Android 手机快速验证智能语音玩具功能  
> **版本**: v1.0.0  
> **最后更新**: 2026 年 2 月 24 日

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://python.org)
[![Kivy](https://img.shields.io/badge/Kivy-2.3+-green.svg)](https://kivy.org)
[![Android](https://img.shields.io/badge/Android-5.0+-brightgreen.svg)](https://android.com)

---

## 📖 项目简介

这是**儿童智能语音玩具**的旧手机验证版本，使用闲置的 Android 手机快速验证核心功能：

- 🎤 **语音采集** - 使用手机内置麦克风
- 📡 **WebSocket 传输** - 实时音频流上传服务器
- 🤖 **AI 对话** - 集成大语言模型（智谱 AI）实现智能对话
- 🔊 **语音合成** - TTS（edge-tts）将回复转换为语音播放
- 🎯 **语音识别** - Whisper 本地语音识别

**优势**：
- ✅ 零成本（利用闲置手机）
- ✅ 无需额外硬件
- ✅ 无需应用商店发布
- ✅ 快速验证（1-2 天完成）

---

## 🏗️ 系统架构

```
┌─────────────────┐     WebSocket      ┌─────────────────┐
│   Android 手机   │ ◄────────────────► │   FastAPI 服务器  │
│   Kivy APP      │    音频流传输      │   AI + TTS + ASR │
│   (内置麦/喇叭)  │                    │                  │
└─────────────────┘                    └─────────────────┘
                                              │
                                              ▼
                                       ┌─────────────────┐
                                       │   大语言模型     │
                                       │   (智谱 AI)      │
                                       └─────────────────┘
```

---

## 📁 目录结构

```
phone-demo/
├── app/                        # Android APP 代码
│   ├── main.py                # 主程序（稳定版）
│   ├── main_stable.py         # 主程序（带完整日志）
│   ├── toyphone.kv            # Kivy UI 定义
│   ├── requirements.txt       # Python 依赖
│   └── buildozer.spec         # APK 打包配置
├── server/                     # 服务器端
│   ├── server.py              # FastAPI 服务器
│   ├── requirements.txt       # 服务器依赖
│   └── download_whisper_model.py  # Whisper 模型下载脚本
├── docs/                       # 文档
├── .env.example               # 环境变量示例
├── .gitignore                 # Git 忽略配置
└── README.md                  # 本文件
```

---

## 🚀 快速开始

### 方式一：电脑测试（推荐开发）

**1. 启动服务器**:
```bash
cd server
pip install -r requirements.txt

# 配置环境变量
copy ..\.env.example .env
# 编辑 .env 填入 AI_API_KEY

# 启动服务器
python server.py
```

**2. 启动 APP（新窗口）**:
```bash
cd app
pip install -r requirements.txt
python main_stable.py
```

**3. 测试对话**:
- 点击"连接服务器"
- 按住"按住说话"
- 说话后松开
- 等待 AI 回复

---

### 方式二：Pydroid 3 手机测试

**1. 手机安装 Pydroid 3**:
- 从应用商店搜索"Pydroid 3"并安装

**2. 复制代码到手机**:
```
电脑 → USB → 手机存储/Download/toyphone/
```

**3. 安装依赖**:
- 打开 Pydroid 3 → Pip → 安装：`kivy aiohttp pyaudio`

**4. 运行 APP**:
- 打开 `main_stable.py` → 点击运行 ▶

---

### 方式三：APK 打包（正式发布）

**Windows 用户（需要 WSL2）**:
```bash
cd app
./build.sh
```

**APK 输出**: `bin/toyphone-1.0.0-debug.apk`

详细文档：[docs/打包部署指南.md](docs/打包部署指南.md)

---

## 🔧 配置说明

### 环境变量 (.env)

```ini
# AI 服务配置（必需）
AI_API_KEY=your_zhipu_api_key_here

# 服务器配置
HOST=0.0.0.0
PORT=8000
DEBUG=true
```

**获取 AI API Key**:
1. 访问 https://open.bigmodel.cn/
2. 注册账号
3. 创建 API Key

### Whisper 模型下载

**首次使用需要下载语音识别模型**:

```bash
cd server

# 使用镜像下载
set HF_ENDPOINT=https://hf-mirror.com
python download_whisper_model.py

# 输入 y 确认下载
```

详细文档：[docs/语音识别部署说明.md](docs/语音识别部署说明.md)

---

## 📱 APP 使用说明

### 界面说明

```
┌─────────────────────────────┐
│   儿童智能语音玩具           │
│                             │
│   状态：已连接 (绿色)        │
│                             │
│   ┌─────────────────────┐   │
│   │                     │   │
│   │   AI 回复文本显示     │   │
│   │                     │   │
│   └─────────────────────┘   │
│                             │
│   [连接服务器] [按住说话]   │
│                             │
│   日志：                     │
│   [10:30:15] 连接成功        │
│   [10:30:20] 发送成功        │
└─────────────────────────────┘
```

### 操作流程

1. **连接服务器**
   - 点击"连接服务器"按钮
   - 状态变为"已连接"（绿色）

2. **开始对话**
   - 按住"按住说话"按钮
   - 对着手机说话
   - 松开按钮，发送录音

3. **接收回复**
   - 屏幕显示 AI 回复文本
   - 自动播放 TTS 语音

---

## 📊 性能指标

| 指标 | 目标 | 实际 |
|------|------|------|
| 连接延迟 | < 100ms | ~50ms |
| 录音质量 | 16kHz 16bit | ✓ |
| AI 响应时间 | < 3s | ~2s |
| TTS 质量 | 可懂 | ✓ |
| 语音识别 | Whisper | ✓ |

---

## 📚 文档索引

### 快速开始
- [快速开始.md](docs/快速开始.md) - 5 分钟体验
- [Pydroid3 安装指南.md](docs/Pydroid3 安装指南.md) - 手机测试

### 部署相关
- [打包部署指南.md](docs/打包部署指南.md) - APK 打包
- [APK 安装说明.md](docs/APK 安装说明.md) - 安装指南
- [服务器部署说明.md](docs/服务器部署说明.md) - 服务器部署
- [语音识别部署说明.md](docs/语音识别部署说明.md) - Whisper 模型配置

### 故障排查
- [故障排查指南.md](docs/故障排查指南.md) - 常见问题
- [部署方式对比.md](docs/部署方式对比.md) - 方案选择

### 日志系统
- [日志管理指南.md](docs/日志管理指南.md) - 日志配置
- [日志优化说明.md](docs/日志优化说明.md) - 日志优化

---

## 🔄 下一步：迁移到 ESP32-S3

验证成功后，代码可无缝迁移到 ESP32-S3 硬件：

| 组件 | 手机方案 | ESP32 方案 |
|------|----------|------------|
| 麦克风 | 内置 | INMP441 |
| 喇叭 | 内置 | MAX98357A + 3W |
| WiFi | 内置 | ESP32-S3 |
| 电池 | 内置 | 18650 |
| UI | 触摸屏 | 按键 + LED |
| 代码 | Python | MicroPython |

**迁移工作量**: 约 2-3 天

---

## 📄 许可证

MIT License

---

*最后更新：2026 年 2 月 24 日*
