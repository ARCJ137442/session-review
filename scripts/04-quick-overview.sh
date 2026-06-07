#!/bin/bash
# 04-quick-overview.sh
# 一句话查看今天/本周的 Claude Code 会话概况
# 用法: bash 04-quick-overview.sh [today|week|all]
#
# 注意: 此脚本依赖 Python (调用 02-scan-all-projects.py)
# 在 Windows (Git Bash/MSYS2) 和 Linux/macOS 上均可运行

MODE=${1:-today}

case "$MODE" in
    today)  DAYS=1 ;;
    week)   DAYS=7 ;;
    all)    DAYS=0 ;;
    *)      DAYS=7 ;;
esac

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# 尝试定位 Python
PYTHON=""
for p in python3 python "/d/Program Files/Python311/python"; do
    if command -v "$p" &>/dev/null || [ -x "$p" ]; then
        PYTHON="$p"
        break
    fi
done

if [ -z "$PYTHON" ]; then
    echo "Error: Python not found"
    exit 1
fi

"$PYTHON" "$SCRIPT_DIR/02-scan-all-projects.py" --days "$DAYS"
