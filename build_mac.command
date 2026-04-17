#!/bin/bash
cd "$(dirname "$0")"

echo "=== Tiger Release Branch Helper - Mac Build ==="
echo ""

echo "[1/3] 安裝依賴套件..."
pip3 install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "❌ pip 安裝失敗，請確認已安裝 Python 3"
    read -p "按 Enter 關閉..."
    exit 1
fi

echo ""
echo "[2/3] 打包 EXE..."
python3 -m PyInstaller \
    --onefile \
    --windowed \
    --name "TigerReleaseBranchHelper" \
    --add-data "*.py:." \
    main.py

if [ $? -ne 0 ]; then
    echo "❌ 打包失敗"
    read -p "按 Enter 關閉..."
    exit 1
fi

echo ""
echo "✅ 打包完成！執行檔在 dist/TigerReleaseBranchHelper"
echo ""
open dist/
read -p "按 Enter 關閉..."
