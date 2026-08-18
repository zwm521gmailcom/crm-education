#!/bin/bash
# =====================================================
# 教培 CRM macOS / Linux 一键启动脚本
# 用法: bash start.sh
# 或:   ./start.sh   (需要先 chmod +x)
# =====================================================
set -e

cd "$(dirname "$0")"

PORT="${PORT:-5050}"
HOST="${HOST:-127.0.0.1}"
export PORT HOST

# 简单的 ASCII banner
echo "==================================="
echo "      教培 CRM 启动器 v1.1"
echo "==================================="
echo "  平台: $(uname -s)"
echo "  端口: $PORT"
echo

# 检查 python3
if ! command -v python3 >/dev/null 2>&1; then
    echo "❌ 未找到 python3,请先安装 Python 3.10+"
    echo "   macOS: brew install python@3.12"
    echo "   Ubuntu: sudo apt install python3 python3-pip python3-venv"
    exit 1
fi

PY_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "[.] Python $PY_VERSION"

# 检查 / 创建 venv
if [ ! -d "venv" ] || [ ! -f "venv/bin/python" ]; then
    echo "[.] 创建虚拟环境 venv/ ..."
    python3 -m venv venv
fi

# shellcheck disable=SC1091
source venv/bin/activate

echo "[.] 安装/更新依赖 ..."
pip install -q -r requirements.txt

# 端口检查(简单)
if lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "⚠️  端口 $PORT 已被占用,先尝试开浏览器看看是不是已经跑起来了"
    if command -v open >/dev/null; then
        open "http://$HOST:$PORT"
    fi
    exit 0
fi

echo "[.] 启动服务(数据库会自动初始化)..."
echo
python3 run.py
