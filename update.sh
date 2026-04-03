#!/bin/bash

# NekoCloud 一键更新脚本 (Ubuntu/Debian)
# GitHub: https://github.com/llulun/NekoCloud

set -euo pipefail

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

INSTALL_DIR="/opt/NekoCloud"
BACKUP_DIR="/opt/NekoCloud_update_backups"

# 检查是否以 root 运行
if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}错误: 请使用 root 用户运行此脚本。${NC}"
   echo -e "请尝试使用: ${YELLOW}sudo bash update.sh${NC}"
   exit 1
fi

echo -e "${BLUE}====================================================${NC}"
echo -e "${BLUE}       🔄 NekoCloud (猫猫云) 一键更新脚本       ${NC}"
echo -e "${BLUE}====================================================${NC}"
echo ""

if [ ! -d "$INSTALL_DIR" ]; then
    echo -e "${RED}错误: 未检测到安装目录 ${INSTALL_DIR}${NC}"
    echo -e "请先执行一键安装脚本。"
    exit 1
fi

cd "$INSTALL_DIR"

if [ ! -d ".git" ]; then
    echo -e "${RED}错误: ${INSTALL_DIR} 不是一个 Git 仓库，无法自动更新。${NC}"
    exit 1
fi

echo -e "${YELLOW}[1/5] 创建更新前备份...${NC}"
mkdir -p "$BACKUP_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
CURRENT_BACKUP="$BACKUP_DIR/update_backup_${TIMESTAMP}"
mkdir -p "$CURRENT_BACKUP"

if [ -f config.json ]; then
    cp config.json "$CURRENT_BACKUP/config.json"
fi

if [ -d backups ]; then
    cp -r backups "$CURRENT_BACKUP/backups"
fi

echo -e "${YELLOW}[2/5] 拉取最新代码...${NC}"
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
git fetch origin "$CURRENT_BRANCH"
git pull --ff-only origin "$CURRENT_BRANCH"

echo -e "${YELLOW}[3/5] 更新 Python 依赖...${NC}"
if [ ! -d venv ]; then
    python3 -m venv venv
fi

source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install waitress

echo -e "${YELLOW}[4/5] 重载并重启服务...${NC}"
if systemctl list-unit-files | grep -q '^nekocloud\.service'; then
    systemctl daemon-reload
    systemctl restart nekocloud
else
    echo -e "${YELLOW}未检测到 systemd 服务 nekocloud，跳过服务重启。${NC}"
fi

echo -e "${YELLOW}[5/5] 检查服务状态...${NC}"
if systemctl list-unit-files | grep -q '^nekocloud\.service'; then
    if systemctl is-active --quiet nekocloud; then
        echo -e "${GREEN}✅ 更新完成，nekocloud 服务运行正常。${NC}"
    else
        echo -e "${RED}❌ 更新后服务未正常运行。${NC}"
        echo -e "请执行 ${YELLOW}systemctl status nekocloud${NC} 查看日志。"
        exit 1
    fi
else
    echo -e "${GREEN}✅ 代码与依赖已更新（未托管 systemd 服务）。${NC}"
fi

echo ""
echo -e "${BLUE}备份位置: ${NC}${CURRENT_BACKUP}"
echo -e "${BLUE}当前分支: ${NC}${CURRENT_BRANCH}"
echo -e "${BLUE}====================================================${NC}"
