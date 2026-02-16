#!/bin/bash

# NekoCloud 一键安装脚本 (Ubuntu/Debian)
# GitHub: https://github.com/llulun/NekoCloud

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 检查是否以 root 运行
if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}错误: 请使用 root 用户运行此脚本。${NC}" 
   echo -e "请尝试使用: ${YELLOW}sudo bash install.sh${NC}"
   exit 1
fi

echo -e "${BLUE}====================================================${NC}"
echo -e "${BLUE}       🐱 NekoCloud (猫猫云) 一键安装脚本       ${NC}"
echo -e "${BLUE}====================================================${NC}"
echo ""

# 1. 更新系统并安装依赖
echo -e "${YELLOW}[1/5] 更新系统软件包...${NC}"
apt-get update -y
echo -e "${YELLOW}[1/5] 安装必要依赖 (Python3, pip, git)...${NC}"
apt-get install -y python3 python3-pip python3-venv git

# 2. 拉取代码
INSTALL_DIR="/opt/NekoCloud"
REPO_URL="https://github.com/llulun/NekoCloud.git"

if [ -d "$INSTALL_DIR" ]; then
    echo -e "${YELLOW}[2/5] 检测到已安装，正在备份旧文件...${NC}"
    mv "$INSTALL_DIR" "${INSTALL_DIR}_backup_$(date +%Y%m%d%H%M%S)"
fi

echo -e "${YELLOW}[2/5] 正在从 GitHub 拉取最新代码...${NC}"
git clone "$REPO_URL" "$INSTALL_DIR"

if [ ! -d "$INSTALL_DIR" ]; then
    echo -e "${RED}错误: 代码拉取失败，请检查网络连接。${NC}"
    exit 1
fi

cd "$INSTALL_DIR"

# 3. 创建虚拟环境并安装依赖
echo -e "${YELLOW}[3/5] 创建 Python 虚拟环境...${NC}"
python3 -m venv venv
source venv/bin/activate

echo -e "${YELLOW}[3/5] 安装 Python 依赖库...${NC}"
pip install --upgrade pip
pip install -r requirements.txt
pip install waitress # 生产环境服务器

# 4. 创建系统服务 (Systemd)
echo -e "${YELLOW}[4/5] 配置系统服务 (Systemd)...${NC}"
SERVICE_FILE="/etc/systemd/system/nekocloud.service"

cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=NekoCloud Web Panel
After=network.target

[Service]
User=root
WorkingDirectory=$INSTALL_DIR
Environment="PATH=$INSTALL_DIR/venv/bin"
ExecStart=$INSTALL_DIR/venv/bin/waitress-serve --port=5001 app:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable nekocloud
systemctl start nekocloud

# 5. 检查服务状态
echo -e "${YELLOW}[5/5] 检查服务运行状态...${NC}"
sleep 3
if systemctl is-active --quiet nekocloud; then
    # 获取本机 IP
    IP=$(curl -s http://checkip.amazonaws.com)
    if [ -z "$IP" ]; then
        IP="服务器IP"
    fi

    echo ""
    echo -e "${GREEN}🎉 NekoCloud 安装成功！${NC}"
    echo -e "${BLUE}====================================================${NC}"
    echo -e "🏠 访问地址: ${GREEN}http://$IP:5001${NC}"
    echo -e "🔧 后台地址: ${GREEN}http://$IP:5001/admin${NC}"
    echo ""
    echo -e "👤 默认账号: ${YELLOW}admin${NC}"
    echo -e "🔑 默认密码: ${YELLOW}adminpassword${NC}"
    echo -e "${BLUE}====================================================${NC}"
    echo -e "${RED}⚠️  注意: 请务必登录后台修改默认密码！${NC}"
    echo -e "如果是云服务器，请确保在防火墙/安全组放行 ${YELLOW}5001${NC} 端口。"
else
    echo -e "${RED}❌ 安装可能失败，服务未能启动。${NC}"
    echo -e "请运行 ${YELLOW}systemctl status nekocloud${NC} 查看错误日志。"
fi
