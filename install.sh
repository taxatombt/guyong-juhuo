#!/bin/bash
#
# 聚活 (guyong-juhuo) 一键安装脚本 — macOS/Linux 版本
# 自动克隆项目、安装依赖、准备运行环境
#

set -e

# 颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}  聚活 (guyong-juhuo) 一键安装${NC}"
echo -e "${CYAN}  打造你自己的个人数字分身${NC}"
echo -e "${CYAN}========================================${NC}"
echo ""

# 检查 Python
if command -v python3 &> /dev/null; then
    PYTHON=python3
    PYVERSION=$(python3 --version)
    echo -e "${GREEN}[OK] 检测到 Python: $PYVERSION${NC}"
else
    if command -v python &> /dev/null; then
        PYTHON=python
        PYVERSION=$(python --version)
        echo -e "${GREEN}[OK] 检测到 Python: $PYVERSION${NC}"
    else
        echo -e "${RED}[错误] 未检测到 Python，请先安装 Python 3.8 或更高版本${NC}"
        echo -e "${YELLOW}  推荐: https://www.python.org/downloads/${NC}"
        exit 1
    fi
fi

# 检查 Git
if command -v git &> /dev/null; then
    GITVERSION=$(git --version)
    echo -e "${GREEN}[OK] 检测到 Git: $GITVERSION${NC}"
else
    echo -e "${RED}[错误] 未检测到 Git，请先安装 Git${NC}"
    exit 1
fi

echo ""
echo -e "${BLUE}[1/4] 克隆项目...${NC}"

if [ -d "guyong-juhuo" ]; then
    echo -e "${YELLOW}[INFO] 项目目录已存在，跳过克隆${NC}"
else
    git clone https://github.com/taxatombt/guyong-juhuo.git
    if [ $? -ne 0 ]; then
        echo -e "${RED}[错误] 克隆失败，请检查网络${NC}"
        exit 1
    fi
fi

cd guyong-juhuo

echo ""
echo -e "${BLUE}[2/4] 升级 pip...${NC}"
$PYTHON -m pip install --upgrade pip

echo ""
echo -e "${BLUE}[3/4] 安装依赖...${NC}"
$PYTHON -m pip install -r requirements.txt

if [ $? -ne 0 ]; then
    echo -e "${YELLOW}[警告] 部分依赖安装失败，请检查网络后重试${NC}"
else
    echo -e "${GREEN}[OK] 依赖安装完成${NC}"
fi

echo ""
echo -e "${BLUE}[4/4] 验证安装...${NC}"
$PYTHON test_all_imports.py

if [ $? -ne 0 ]; then
    echo ""
    echo -e "${YELLOW}[警告] 部分模块验证失败，但不影响基础使用${NC}"
else
    echo -e "${GREEN}[OK] 所有模块验证通过${NC}"
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}             安装完成！${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "启动网页控制台:${NC}"
echo -e "  ${CYAN}cd guyong-juhuo${NC}"
echo -e "  ${CYAN}python web_console.py${NC}"
echo ""
echo -e "然后打开浏览器访问: ${CYAN}http://127.0.0.1:9876${NC}"
echo ""
echo -e "${CYAN}祝你使用愉快！🎯 聚活 — 记住你的一切，代替你永远活下去${NC}"
echo ""
