#!/usr/bin/env bash
#
# Nexus AI Works — 一键安装启动脚本
#
# 用法:
#   ./setup.sh         交互式安装启动
#   ./setup.sh --dev   开发者模式（前后端分离）
#   ./setup.sh --help  查看帮助
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

log()  { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err()  { echo -e "${RED}[✗]${NC} $1"; }
info() { echo -e "${CYAN}[i]${NC} $1"; }

# ── Parse args ────────────────────────────────────────────────

DEV_MODE=false
case "${1:-}" in
  --dev) DEV_MODE=true; shift ;;
  --help|-h)
    echo "Nexus AI Works 一键安装启动脚本"
    echo ""
    echo "用法: ./setup.sh [选项]"
    echo ""
    echo "选项:"
    echo "  --dev    开发者模式（前后端分开启动，需要两个终端）"
    echo "  --help   显示此帮助"
    exit 0
    ;;
esac

# ── Banner ────────────────────────────────────────────────────

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║       Nexus AI Works 安装启动程序         ║${NC}"
echo -e "${CYAN}║              v1.0.0                       ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════╝${NC}"
echo ""

# ── Check Python ──────────────────────────────────────────────

info "检查 Python ..."
PYTHON=""
for candidate in python3 python; do
  if command -v "$candidate" &>/dev/null; then
    ver=$("$candidate" --version 2>&1 | grep -oE '[0-9]+\.[0-9]+' | head -1)
    major=$(echo "$ver" | cut -d. -f1)
    minor=$(echo "$ver" | cut -d. -f2)
    if [ "$major" -ge 3 ] && [ "$minor" -ge 11 ]; then
      PYTHON="$candidate"
      log "Python $ver"
      break
    fi
  fi
done

if [ -z "$PYTHON" ]; then
  err "需要 Python 3.11+，请先安装: https://www.python.org/downloads/"
  exit 1
fi

# ── Check Node.js ─────────────────────────────────────────────

info "检查 Node.js ..."
NODE=""
for candidate in node; do
  if command -v "$candidate" &>/dev/null; then
    ver=$("$candidate" --version 2>&1 | grep -oE '[0-9]+' | head -1)
    if [ "$ver" -ge 18 ]; then
      NODE="$candidate"
      log "Node.js $("$candidate" --version)"
      break
    fi
  fi
done

if [ -z "$NODE" ]; then
  err "需要 Node.js 18+，请先安装: https://nodejs.org/"
  exit 1
fi

# ── Install Python dependencies ───────────────────────────────

info "安装 Python 依赖 ..."
if [ ! -d ".venv" ]; then
  "$PYTHON" -m venv .venv
  log "创建虚拟环境 .venv"
fi

# shellcheck disable=SC1091
source .venv/bin/activate
pip install -e . --quiet 2>&1 | tail -3
log "Python 依赖安装完成"

# ── Install frontend dependencies ─────────────────────────────

if [ -d "webui" ]; then
  info "安装前端依赖 ..."
  cd webui
  npm install --silent 2>&1 | tail -3
  log "前端依赖安装完成"
  cd "$SCRIPT_DIR"
fi

# ── Build frontend (production mode) ──────────────────────────

if [ "$DEV_MODE" = false ]; then
  info "构建前端 ..."
  cd webui
  npm run build --silent 2>&1 | tail -3
  log "前端构建完成"
  cd "$SCRIPT_DIR"
fi

# ── Start ─────────────────────────────────────────────────────

echo ""
echo -e "${GREEN}══════════════════════════════════════════${NC}"
echo -e "${GREEN}  安装完成！正在启动 Nexus AI Works ...${NC}"
echo -e "${GREEN}══════════════════════════════════════════${NC}"
echo ""

if [ "$DEV_MODE" = true ]; then
  # Developer mode: two terminals
  info "开发者模式 — 在另一个终端中运行:"
  echo "   cd webui && npm run dev"
  echo ""
  info "启动 Gateway (端口 8600) ..."
  "$PYTHON" entrypoint.py serve
else
  # Production mode: both in one
  info "启动 Nexus AI Works ..."
  info "Gateway: http://127.0.0.1:8600"
  info "WebUI:  http://127.0.0.1:8600 (内嵌前端)"

  # Open browser after a short delay
  sleep 2
  if command -v open &>/dev/null; then
    open "http://127.0.0.1:8600" 2>/dev/null || true
  elif command -v xdg-open &>/dev/null; then
    xdg-open "http://127.0.0.1:8600" 2>/dev/null || true
  fi

  "$PYTHON" entrypoint.py serve
fi
