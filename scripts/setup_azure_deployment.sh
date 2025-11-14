#!/bin/bash

# Azure 自動部署快速設置腳本
# 此腳本幫助您快速設置 GitHub Actions 部署到 Azure

set -e

# 顏色輸出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Azure 自動部署設置腳本                         ║${NC}"
echo -e "${BLUE}║   Call Center AI - 2025                          ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════╝${NC}"
echo ""

# 檢查先決條件
echo -e "${YELLOW}📋 檢查先決條件...${NC}"

if ! command -v az &> /dev/null; then
    echo -e "${RED}❌ Azure CLI 未安裝${NC}"
    echo "請安裝 Azure CLI: https://docs.microsoft.com/cli/azure/install-azure-cli"
    exit 1
fi
echo -e "${GREEN}✅ Azure CLI 已安裝${NC}"

if ! command -v gh &> /dev/null; then
    echo -e "${YELLOW}⚠️  GitHub CLI 未安裝（可選）${NC}"
    echo "如需自動配置 GitHub Secrets，請安裝: https://cli.github.com/"
    GH_CLI_AVAILABLE=false
else
    echo -e "${GREEN}✅ GitHub CLI 已安裝${NC}"
    GH_CLI_AVAILABLE=true
fi

if ! command -v jq &> /dev/null; then
    echo -e "${RED}❌ jq 未安裝${NC}"
    echo "請安裝 jq: https://stedolan.github.io/jq/download/"
    exit 1
fi
echo -e "${GREEN}✅ jq 已安裝${NC}"

echo ""

# 登入 Azure
echo -e "${YELLOW}🔐 Azure 登入...${NC}"
if ! az account show &> /dev/null; then
    az login
else
    echo -e "${GREEN}✅ 已登入 Azure${NC}"
fi

# 選擇訂閱
echo ""
echo -e "${YELLOW}📋 選擇 Azure 訂閱...${NC}"
az account list --output table

echo ""
read -p "請輸入訂閱 ID（按 Enter 使用當前訂閱）: " SUBSCRIPTION_ID

if [ -n "$SUBSCRIPTION_ID" ]; then
    az account set --subscription "$SUBSCRIPTION_ID"
fi

SUBSCRIPTION_ID=$(az account show --query id --output tsv)
SUBSCRIPTION_NAME=$(az account show --query name --output tsv)
TENANT_ID=$(az account show --query tenantId --output tsv)

echo -e "${GREEN}✅ 使用訂閱: $SUBSCRIPTION_NAME ($SUBSCRIPTION_ID)${NC}"

# 設定變數
echo ""
echo -e "${YELLOW}⚙️  設定部署參數...${NC}"

read -p "應用程式名稱 [call-center-ai]: " APP_NAME
APP_NAME=${APP_NAME:-call-center-ai}

read -p "服務主體名稱 [${APP_NAME}-github-actions]: " SP_NAME
SP_NAME=${SP_NAME:-${APP_NAME}-github-actions}

read -p "GitHub 倉庫（格式: owner/repo）[Cloudinfo-Github/call-center-ai]: " GITHUB_REPO
GITHUB_REPO=${GITHUB_REPO:-Cloudinfo-Github/call-center-ai}

echo ""
echo -e "${BLUE}📝 配置摘要:${NC}"
echo "  訂閱: $SUBSCRIPTION_NAME"
echo "  應用程式: $APP_NAME"
echo "  服務主體: $SP_NAME"
echo "  GitHub 倉庫: $GITHUB_REPO"
echo ""

read -p "確認以上配置？(y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${RED}❌ 已取消${NC}"
    exit 1
fi

# 創建服務主體
echo ""
echo -e "${YELLOW}🔑 創建 Azure 服務主體...${NC}"

# 檢查服務主體是否已存在
EXISTING_SP=$(az ad sp list --display-name "$SP_NAME" --query "[0].appId" --output tsv)

if [ -n "$EXISTING_SP" ]; then
    echo -e "${YELLOW}⚠️  服務主體 '$SP_NAME' 已存在${NC}"
    read -p "是否刪除並重新創建？(y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        az ad sp delete --id "$EXISTING_SP"
        echo -e "${GREEN}✅ 已刪除舊的服務主體${NC}"
    else
        CLIENT_ID=$EXISTING_SP
        echo -e "${YELLOW}⚠️  使用現有的服務主體${NC}"
    fi
fi

if [ -z "$CLIENT_ID" ]; then
    # 創建新的服務主體
    SP_OUTPUT=$(az ad sp create-for-rbac \
        --name "$SP_NAME" \
        --role contributor \
        --scopes "/subscriptions/$SUBSCRIPTION_ID" \
        --sdk-auth)

    CLIENT_ID=$(echo "$SP_OUTPUT" | jq -r '.clientId')
    CLIENT_SECRET=$(echo "$SP_OUTPUT" | jq -r '.clientSecret')

    echo -e "${GREEN}✅ 服務主體已創建${NC}"
    echo "  Client ID: $CLIENT_ID"
fi

# 配置 OIDC 聯合憑證
echo ""
echo -e "${YELLOW}🔐 配置 OIDC 聯合憑證（更安全）...${NC}"

APP_OBJECT_ID=$(az ad app list --display-name "$SP_NAME" --query "[0].id" --output tsv)

if [ -z "$APP_OBJECT_ID" ]; then
    echo -e "${RED}❌ 無法找到應用程式物件 ID${NC}"
    exit 1
fi

# 為 main 分支創建聯合憑證
echo "  創建 main 分支憑證..."
az ad app federated-credential create \
    --id "$APP_OBJECT_ID" \
    --parameters "{
        \"name\": \"github-main\",
        \"issuer\": \"https://token.actions.githubusercontent.com\",
        \"subject\": \"repo:$GITHUB_REPO:ref:refs/heads/main\",
        \"audiences\": [\"api://AzureADTokenExchange\"]
    }" 2>/dev/null || echo "  （憑證可能已存在）"

# 為環境創建聯合憑證
for ENV in development staging production; do
    echo "  創建 $ENV 環境憑證..."
    az ad app federated-credential create \
        --id "$APP_OBJECT_ID" \
        --parameters "{
            \"name\": \"github-$ENV\",
            \"issuer\": \"https://token.actions.githubusercontent.com\",
            \"subject\": \"repo:$GITHUB_REPO:environment:$ENV\",
            \"audiences\": [\"api://AzureADTokenExchange\"]
        }" 2>/dev/null || echo "  （憑證可能已存在）"
done

echo -e "${GREEN}✅ OIDC 聯合憑證已配置${NC}"

# 顯示需要設定的 Secrets
echo ""
echo -e "${BLUE}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   GitHub Secrets 配置                            ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════╝${NC}"
echo ""
echo "請在 GitHub 設定以下 Secrets:"
echo ""
echo -e "${YELLOW}名稱: AZURE_CLIENT_ID${NC}"
echo "值: $CLIENT_ID"
echo ""
echo -e "${YELLOW}名稱: AZURE_TENANT_ID${NC}"
echo "值: $TENANT_ID"
echo ""
echo -e "${YELLOW}名稱: AZURE_SUBSCRIPTION_ID${NC}"
echo "值: $SUBSCRIPTION_ID"
echo ""

if [ -n "$CLIENT_SECRET" ]; then
    echo -e "${YELLOW}名稱: AZURE_CLIENT_SECRET${NC}"
    echo "值: $CLIENT_SECRET"
    echo -e "${BLUE}（使用 OIDC 時不需要此 Secret）${NC}"
    echo ""
fi

# 使用 GitHub CLI 自動配置
if [ "$GH_CLI_AVAILABLE" = true ]; then
    echo ""
    read -p "使用 GitHub CLI 自動配置 Secrets？(y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}🔑 配置 GitHub Secrets...${NC}"

        # 檢查是否已登入 GitHub CLI
        if ! gh auth status &> /dev/null; then
            echo "請先登入 GitHub CLI..."
            gh auth login
        fi

        # 設定 Secrets
        echo "$CLIENT_ID" | gh secret set AZURE_CLIENT_ID --repo "$GITHUB_REPO"
        echo "$TENANT_ID" | gh secret set AZURE_TENANT_ID --repo "$GITHUB_REPO"
        echo "$SUBSCRIPTION_ID" | gh secret set AZURE_SUBSCRIPTION_ID --repo "$GITHUB_REPO"

        if [ -n "$CLIENT_SECRET" ]; then
            echo "$CLIENT_SECRET" | gh secret set AZURE_CLIENT_SECRET --repo "$GITHUB_REPO"
        fi

        echo -e "${GREEN}✅ GitHub Secrets 已配置${NC}"
    fi
fi

# 儲存配置
echo ""
echo -e "${YELLOW}💾 儲存配置到本地...${NC}"

CONFIG_FILE=".azure-deployment-config"
cat > "$CONFIG_FILE" << EOF
# Azure 部署配置
# 此檔案包含敏感資訊，請勿提交到 Git
AZURE_CLIENT_ID=$CLIENT_ID
AZURE_TENANT_ID=$TENANT_ID
AZURE_SUBSCRIPTION_ID=$SUBSCRIPTION_ID
GITHUB_REPO=$GITHUB_REPO
APP_NAME=$APP_NAME
EOF

# 確保 .gitignore 包含配置檔案
if ! grep -q ".azure-deployment-config" .gitignore 2>/dev/null; then
    echo ".azure-deployment-config" >> .gitignore
    echo -e "${GREEN}✅ 已將配置檔案添加到 .gitignore${NC}"
fi

echo -e "${GREEN}✅ 配置已儲存到 $CONFIG_FILE${NC}"

# 完成
echo ""
echo -e "${BLUE}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   設置完成！🎉                                    ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${GREEN}下一步:${NC}"
echo "1. 確認 GitHub Secrets 已正確設定"
echo "2. 在 GitHub 中創建環境（development, staging, production）"
echo "3. 測試部署："
echo ""
echo "   前往: https://github.com/$GITHUB_REPO/actions"
echo "   選擇: Deploy to Azure → Run workflow"
echo ""
echo -e "${YELLOW}📚 更多資訊請參考: docs/AZURE_DEPLOYMENT_SETUP.md${NC}"
echo ""
