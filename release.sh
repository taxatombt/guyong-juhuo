#!/bin/bash
# release.sh - 打包 + 打 tag + 打开 Release 页面
# 用法: bash release.sh [tag名]
# 网络恢复后运行：cd /d E:\juhuo && bash release.sh v2.0.0

set -e
TAG=${1:-$(date +v%Y.%m.%d)}

echo "=== Release $TAG ==="

# 1. 打包
echo "[1/4] PyInstaller..."
cmd /c "cd /d E:\juhuo && E:\qwenpaw\python.exe E:\qwenpaw\Scripts\pyinstaller.exe juhuo.spec --noconfirm"

# 2. 验证
if [ ! -f "dist/guyong-juhuo.exe" ]; then
    echo "ERROR: dist/guyong-juhuo.exe not found"
    exit 1
fi
echo "[2/4] OK: $(ls -lh dist/guyong-juhuo.exe | awk '{print $5}')"

# 3. Git tag + push
echo "[3/4] Git tag + push..."
cd /d E:\juhuo
git tag -a $TAG -m "Release $TAG"
git push origin $TAG

# 4. 打开 Release 页面（手动拖文件）
echo "[4/4] 打开 GitHub Release 页面..."
start "https://github.com/taxatombt/guyong-juhuo/releases/new?tag=$TAG&title=$TAG&draft=false"

echo ""
echo "=== 手动步骤 ==="
echo "1. Release 标题输入: guyong-juhuo $TAG"
echo "2. 说明随便写"
echo "3. 把 dist/guyong-juhuo.exe 拖到上传区域"
echo "4. 点 Publish release"
