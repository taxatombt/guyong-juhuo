#!/bin/bash
# release.sh - 一键发版：文档 + 打包 + tag + 推送 + 打开Release页面
#
# 用法（网络恢复后）:
#   cd /d E:\juhuo && bash release.sh v2.0.0
#
# 规则：每次 git push 之前，必须跑这一句。
#
# 触发条件（满足任一）:
#   - 新功能完成
#   - CLI 命令有变化
#   - 安装/下载流程改了
#   - CHANGELOG / README / INSTALL_GUIDE 有修改
#
# 输出：
#   - dist/guyong-juhuo-setup.exe  （Inno Setup 安装版，约 50MB）
#     注意：不再生成便携版（不需要 portable exe）

set -e
TAG=${1:-$(date +v%Y.%m.%d)}

echo "=== Release $TAG ==="

# 1. 文档 + 源码 提交
echo "[1/6] Git add + commit..."
cd /d E:\juhuo
git add -A
if git diff --cached --quiet; then
    echo "  Nothing to commit (skip)"
else
    git commit -m "Release $TAG"
fi

# 2. PyInstaller 打包
echo "[2/6] PyInstaller..."
cmd /c "cd /d E:\juhuo && E:\qwenpaw\python.exe E:\qwenpaw\Scripts\pyinstaller.exe juhuo.spec --noconfirm"
if [ ! -f "dist/guyong-juhuo.exe" ]; then
    echo "ERROR: dist/guyong-juhuo.exe not found"
    exit 1
fi
echo "  OK: $(ls -lh dist/guyong-juhuo.exe | awk '{print $5}')"

# 3. Inno Setup 安装版
echo "[3/6] Inno Setup（安装版）..."
ISCC=""
for p in "/c/Program Files (x86)/Inno Setup 6/ISCC.exe" "/c/Program Files/Inno Setup 6/ISCC.exe"; do
    if [ -f "$p" ]; then ISCC="$p"; break; fi
done

if [ -z "$ISCC" ]; then
    echo "  WARN: Inno Setup 未安装，跳过安装版"
    echo "  Inno Setup 安装后重新运行: bash release.sh $TAG"
else
    cmd /c "cd /d E:\juhuo && \"$ISCC\" installer.iss"
    if [ -f "dist/guyong-juhuo-setup.exe" ]; then
        echo "  OK: $(ls -lh dist/guyong-juhuo-setup.exe | awk '{print $5}')"
    fi
fi

# 4. 验证 exe
echo "[4/6] 验证 exe..."
cmd /c "E:\juhuo\dist\guyong-juhuo.exe status" > /dev/null 2>&1 && echo "  OK: exe runs" || echo "  WARN: exe may have issues"

# 5. Git tag + push
echo "[5/6] Git push + tag..."
git tag -a $TAG -m "Release $TAG"
git push
git push origin $TAG

# 6. 打开 Release 页面（手动拖 exe 上传）
echo "[6/6] 打开 GitHub Release 页面..."
start "https://github.com/taxatombt/guyong-juhuo/releases/new?tag=$TAG&title=$TAG&draft=false"

echo ""
echo "=== 手动操作 ==="
echo "1. 把 dist/guyong-juhuo-setup.exe 拖到上传区域（有安装版时）"
echo "2. 点 Publish release"
echo ""
echo "Done: https://github.com/taxatombt/guyong-juhuo/releases/tag/$TAG"
