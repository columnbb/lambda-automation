#!/bin/bash

echo "=== Ghost Automation 專案初始化 ==="

PROJECT_ROOT="/home/cloudshell-user/lambda-projects/ghost-automation"

# 建立必要目錄
mkdir -p "$PROJECT_ROOT"/{scripts,layers,config,logs}

# 建立設定檔範本
cat > "$PROJECT_ROOT/config/settings.conf" << 'SETTINGS'
# Ghost Automation 設定檔
LAMBDA_FUNCTION_NAME=GhostPerplexityDemo
LAYER_NAME=prompts-layer
DEPENDENCIES_LAYER_ARN=arn:aws:lambda:ap-southeast-2:324183266130:layer:blockchain-dependencies:1
AWS_REGION=ap-southeast-2
SETTINGS

echo "✅ 專案結構已建立"
echo "✅ 設定檔已建立: $PROJECT_ROOT/config/settings.conf"
echo "✅ 別名已加入 .bashrc"

echo ""
echo "可用別名："
echo "  ghost-update  - 更新提示詞層"
echo "  ghost-cd      - 切換到專案目錄"
echo "  ghost-logs    - 查看執行日誌"

