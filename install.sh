#!/usr/bin/env bash
# wechat-audio-toolkit 一键安装脚本
#
# 用法：
#   curl -fsSL https://raw.githubusercontent.com/guoxiaowen/wechat-audio-toolkit/main/install.sh | bash
#
# 这个脚本干什么：
#   1. 检查 ffmpeg + uv（缺的话用 Homebrew 装）
#   2. 把 wechat-audio-toolkit 仓库 clone 到 ~/wechat-audio-toolkit
#   3. 创建 Python venv 并装依赖
#   4. 提示你下一步要配 ~/.claude/.env

set -e

REPO_URL="https://github.com/guoxiaowen/wechat-audio-toolkit"
INSTALL_DIR="$HOME/wechat-audio-toolkit"

color() { printf "\033[1;32m%s\033[0m\n" "$1"; }
warn()  { printf "\033[1;33m%s\033[0m\n" "$1"; }
error() { printf "\033[1;31m%s\033[0m\n" "$1"; }

color "==> wechat-audio-toolkit installer"

# 1. Homebrew check
if ! command -v brew >/dev/null 2>&1; then
  error "Homebrew 未安装。先去 https://brew.sh/ 装它。"
  exit 1
fi

# 2. ffmpeg
if ! command -v ffmpeg >/dev/null 2>&1; then
  color "==> 安装 ffmpeg..."
  brew install ffmpeg
else
  echo "    ffmpeg：已安装"
fi

# 3. uv
if ! command -v uv >/dev/null 2>&1; then
  color "==> 安装 uv..."
  brew install uv
else
  echo "    uv：已安装"
fi

# 4. Clone or pull
if [ -d "$INSTALL_DIR" ]; then
  warn "==> $INSTALL_DIR 已存在，拉取最新代码..."
  cd "$INSTALL_DIR" && git pull --ff-only
else
  color "==> Clone 仓库到 $INSTALL_DIR..."
  git clone "$REPO_URL" "$INSTALL_DIR"
fi

cd "$INSTALL_DIR"

# 5. Setup venv
color "==> 创建 Python venv..."
uv venv

color "==> 安装 Python 依赖..."
uv sync

# 6. Check ~/.claude/.env
ENV_FILE="$HOME/.claude/.env"
mkdir -p "$HOME/.claude"

if [ ! -f "$ENV_FILE" ]; then
  warn "==> ~/.claude/.env 不存在。"
  warn "    需要你手动创建，包含以下内容（从你旧 Mac 拷过来即可）："
  echo ""
  echo "    DASHSCOPE_API_KEY=sk-..."
  echo "    OSS_ACCESS_KEY_ID=LTAI5t..."
  echo "    OSS_ACCESS_KEY_SECRET=..."
  echo "    OSS_BUCKET=your-bucket-name"
  echo "    OSS_ENDPOINT=oss-cn-beijing.aliyuncs.com"
  echo ""
  warn "    创建后请运行：chmod 600 $ENV_FILE"
  echo ""
  warn "    然后再跑一次：cd $INSTALL_DIR && .venv/bin/python skills/audio-to-wechat-md/scripts/run.py check"
  echo ""
else
  echo "    ~/.claude/.env：已存在"

  # Try check
  color "==> 自检..."
  if .venv/bin/python skills/audio-to-wechat-md/scripts/run.py check 2>&1 | grep -q '"ok": true'; then
    color "    全绿！"
  else
    warn "    check 没通过，可能是 ~/.claude/.env 里某个 key 缺了。手动跑这条看具体报错："
    echo "    cd $INSTALL_DIR && .venv/bin/python skills/audio-to-wechat-md/scripts/run.py check"
  fi
fi

echo ""
color "==> 现在去 Claude Code 把 plugin 注册一下"
echo ""
echo "    打开终端跑：claude"
echo ""
echo "    在 Claude Code 提示符里依次输入："
echo "      /plugin marketplace add $INSTALL_DIR"
echo "      /plugin install wechat-audio-toolkit@wechat-audio-toolkit"
echo ""
echo "    或者一行的 GitHub 直接安装（跳过本地 marketplace）："
echo "      /plugin marketplace add guoxiaowen/wechat-audio-toolkit"
echo "      /plugin install wechat-audio-toolkit@wechat-audio-toolkit"
echo ""
color "完成。"
