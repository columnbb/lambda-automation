#!/bin/bash

# === 智能目錄管理 ===
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LAYERS_DIR="$PROJECT_ROOT/layers"
CONFIG_DIR="$PROJECT_ROOT/config"
LOGS_DIR="$PROJECT_ROOT/logs"

echo "=== Ghost 提示詞層更新腳本 ==="
echo "專案根目錄: $PROJECT_ROOT"
echo "當前時間: $(date '+%Y-%m-%d %H:%M:%S')"

# 確保工作目錄正確
cd "$PROJECT_ROOT"

# 建立日誌檔案
LOG_FILE="$LOGS_DIR/update-$(date +%Y%m%d_%H%M%S).log"
exec 1> >(tee -a "$LOG_FILE")
exec 2>&1

echo "日誌檔案: $LOG_FILE"

# ===== 自動清理舊檔案 ====
echo "正在清理舊提示詞檔案..."
OLD_PROMPT="/home/cloudshell-user/ghost_prompt_tw.txt"
if [ -f "$OLD_PROMPT" ]; then
    rm -f "$OLD_PROMPT"
    echo "✅ 已刪除舊提示詞檔案"
else
    echo "ℹ️ 無舊檔案可刪除"
fi

# ===== 等待新檔案上傳 ====
echo "請上傳新的 ghost_prompt_tw.txt 檔案到 CloudShell 主目錄"
echo "上傳完成後，按 Enter 繼續..."
read -p ""

# ===== 檔案檢查 =====
PROMPT_FILE="/home/cloudshell-user/ghost_prompt_tw.txt"
if [ ! -f "$PROMPT_FILE" ]; then
    echo "❌ 錯誤：找不到提示詞檔案 $PROMPT_FILE"
    echo "請確認已上傳 ghost_prompt_tw.txt 到 CloudShell 主目錄"
    exit 1
fi

echo "✅ 找到提示詞檔案: $PROMPT_FILE"
echo "檔案大小: $(wc -c < "$PROMPT_FILE") bytes"
echo "檔案內容開頭: $(head -n 2 "$PROMPT_FILE")"

# ===== 清理並重建層結構 =====
echo "正在清理舊的層結構..."
rm -rf "$LAYERS_DIR"
mkdir -p "$LAYERS_DIR/assets/prompts"

# 複製提示詞檔案
cp "$PROMPT_FILE" "$LAYERS_DIR/assets/prompts/"
echo "✅ 提示詞檔案已複製到層結構"

# ===== 打包層 =====
cd "$LAYERS_DIR"
ZIP_FILE="prompts-layer-$(date +%Y%m%d_%H%M%S).zip"
zip -r "$ZIP_FILE" assets/

if [ $? -eq 0 ]; then
    echo "✅ 層打包成功: $ZIP_FILE"
else
    echo "❌ 層打包失敗"
    exit 1
fi

# ===== 發佈層版本 =====
echo "正在發佈新層版本..."
LAYER_OUTPUT=$(aws lambda publish-layer-version \
  --layer-name prompts-layer \
  --description "提示詞更新 $(date '+%Y-%m-%d %H:%M:%S')" \
  --zip-file "fileb://$ZIP_FILE" \
  --compatible-runtimes python3.13)

if [ $? -eq 0 ]; then
    echo "✅ 層發佈成功"
    
    # 提取新層版本 ARN（不依賴 jq）
    NEW_LAYER_ARN=$(echo "$LAYER_OUTPUT" | grep -o '"LayerVersionArn": "[^"]*"' | sed 's/"LayerVersionArn": "//; s/"//')
    echo "新層版本 ARN: $NEW_LAYER_ARN"
    
    # 儲存 ARN 到設定檔
    echo "$NEW_LAYER_ARN" > "$CONFIG_DIR/latest-layer-arn.txt"
    
    # ===== 更新 Lambda 函數 =====
    echo "正在更新 Lambda 函數..."
    DEPENDENCIES_ARN="arn:aws:lambda:ap-southeast-2:324183266130:layer:blockchain-dependencies:1"
    
    aws lambda update-function-configuration \
      --function-name GhostPerplexityDemo \
      --layers "$DEPENDENCIES_ARN" "$NEW_LAYER_ARN"
    
    if [ $? -eq 0 ]; then
        echo "✅ Lambda 函數更新成功"
        echo "🎉 提示詞層更新完成！"
    else
        echo "❌ Lambda 函數更新失敗"
        exit 1
    fi
else
    echo "❌ 層發佈失敗"
    exit 1
fi

echo "=== 更新完成 $(date '+%Y-%m-%d %H:%M:%S') ==="
