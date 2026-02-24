#!/bin/bash
# 儿童智能语音玩具 - Android APK 打包脚本
# 适用于 Linux/Mac/WSL2

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 打印横幅
echo "========================================"
echo "  儿童智能语音玩具 - APK 打包工具"
echo "  版本：1.0.0"
echo "========================================"
echo ""

# 检查 Python
log_info "检查 Python 环境..."
if ! command -v python3 &> /dev/null; then
    log_error "Python3 未安装，请先安装 Python 3.8+"
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
log_success "Python 版本：$PYTHON_VERSION"

# 检查虚拟环境
if [ ! -d "venv" ]; then
    log_info "创建虚拟环境..."
    python3 -m venv venv
    log_success "虚拟环境创建完成"
else
    log_info "虚拟环境已存在"
fi

# 激活虚拟环境
log_info "激活虚拟环境..."
source venv/bin/activate

# 检查/安装依赖
log_info "检查依赖..."
pip install -q --upgrade pip

# 安装 buildozer
if ! pip show buildozer &> /dev/null; then
    log_info "安装 Buildozer..."
    pip install -q buildozer cython
    log_success "Buildozer 安装完成"
else
    log_info "Buildozer 已安装"
fi

# 检查 buildozer.spec
if [ ! -f "buildozer.spec" ]; then
    log_error "buildozer.spec 不存在!"
    log_info "请确保在项目根目录运行此脚本"
    exit 1
fi
log_success "配置文件检查通过"

# 检查系统依赖
log_info "检查系统依赖..."

check_package() {
    if dpkg -l "$1" &> /dev/null; then
        return 0
    else
        return 1
    fi
}

# Ubuntu/Debian 检查
if command -v apt &> /dev/null; then
    MISSING_PKGS=()
    
    for pkg in git ffmpeg python3-dev build-essential; do
        if ! check_package "$pkg"; then
            MISSING_PKGS+=("$pkg")
        fi
    done
    
    if [ ${#MISSING_PKGS[@]} -gt 0 ]; then
        log_warning "缺少依赖：${MISSING_PKGS[*]}"
        log_info "安装缺失的依赖..."
        sudo apt install -y "${MISSING_PKGS[@]}"
    fi
fi

log_success "系统依赖检查完成"

# 清理旧构建 (可选)
if [ -d "bin" ] && [ "$(ls -A bin)" ]; then
    log_info "清理旧的构建文件..."
    rm -rf bin/
fi

# 开始打包
echo ""
echo "========================================"
echo "  开始打包 APK"
echo "========================================"
echo ""

log_info "Buildozer 打包中... (首次运行约 60-90 分钟)"
log_info "进度信息将实时显示："
echo ""

# 运行 buildozer
buildozer -v android debug

# 检查输出
echo ""
if [ -f "bin/toyphone-1.0.0-debug.apk" ]; then
    APK_SIZE=$(du -h "bin/toyphone-1.0.0-debug.apk" | cut -f1)
    log_success "打包成功!"
    log_info "APK 文件：bin/toyphone-1.0.0-debug.apk"
    log_info "APK 大小：$APK_SIZE"
    echo ""
    echo "========================================"
    echo "  下一步操作"
    echo "========================================"
    echo ""
    echo "1. 将 APK 传输到手机"
    echo "2. 手机允许'未知来源'安装"
    echo "3. 安装并运行 APP"
    echo ""
    echo "详细安装说明见：docs/打包部署指南.md"
    echo ""
else
    log_error "打包失败！请检查错误日志"
    exit 1
fi
