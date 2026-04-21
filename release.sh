#!/bin/bash
# release.sh - 一键发版：文档 + 打包 + tag + 推送 + 打开Release页面
#
# 用法（网络恢复后）:
#   cd /d E:\juhuo && bash release.sh v2.0.0
#
# 规则：每次 git push 之前，必须跑这一句。
# 触发条件（满足任一）:
#   - 新功能完成
#   - CLI 命令有变化
#   - 安装/下载流程改了
#   - CHANGELOG / README / INSTALL_GUIDE 有修改

set -e
TAG=${1:-$(date +v%Y.%m.%d)}

echo "=== Release $TAG ==="

# 1. 文档 + 源码 提交
echo "[1/5] Git add + commit..."
cd /d E:\juhuo
git add -A
if git diff --cached --quiet; then
    echo "  Nothing to commit (skip)"
else
    git commit -m "Release $TAG"
fi

# 2. PyInstaller 打包
echo "[2/5] PyInstaller..."
cmd /c "cd /d E:\juhuo && E:\qwenpaw\python.exe E:\qwenpaw\Scripts\pyinstaller.exe juhuo.spec --noconfirm"
if [ ! -f "dist/guyong-juhuo.exe" ]; then
    echo "ERROR: dist/guyong-juhuo.exe not found"
    exit 1
fi
echo "  OK: $(ls -lh dist/guyong-juhuo.exe | awk '{print $5}')"

# 3. 验证 exe
echo "[3/5] 验证 exe..."
cmd /c "E:\juhuo\dist\guyong-juhuo.exe status" > /dev/null 2>&1 && echo "  OK: exe runs" || echo "  WARN: exe may have issues"

# 4. Git tag + push
echo "[4/5] Git push + tag..."
git tag -a $TAG -m "Release $TAG"
git push
git push origin $TAG

# 5. 打开 Release 页面（手动拖 exe 上传）
echo "[5/5] 打开 GitHub Release 页面..."
start "https://github.com/taxatombt/guyong-juhuo/releases/new?tag=$TAG&title=$TAG&draft=false"

echo ""
echo "=== 手动操作 ==="
echo "1. 把 dist/guyong-juhuo.exe 拖到上传区域"
echo "2. 点 Publish release"
echo ""
echo "Done: https://github.com/taxatombt/guyong-juhuo/releases/tag/$TAG"
