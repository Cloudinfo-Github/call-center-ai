# Azure 自動部署設置指南

本指南將幫助您設置 GitHub Actions 自動部署到 Azure。

---

## 📋 前置要求

- Azure 訂閱
- GitHub 帳號
- Azure CLI 已安裝
- 專案的管理員權限

---

## 🔐 步驟一：創建 Azure 服務主體（Service Principal）

### 1. 登入 Azure

```bash
az login
az account set --subscription "<your-subscription-id>"
```

### 2. 創建服務主體

```bash
# 設定變數
SUBSCRIPTION_ID=$(az account show --query id --output tsv)
RESOURCE_GROUP="call-center-ai-dev"
APP_NAME="call-center-ai-github-actions"

# 創建服務主體（使用 OIDC）
az ad sp create-for-rbac \
  --name "${APP_NAME}" \
  --role contributor \
  --scopes /subscriptions/${SUBSCRIPTION_ID} \
  --sdk-auth
```

### 3. 保存輸出

您會看到類似以下的 JSON 輸出，**請妥善保存**：

```json
{
  "clientId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "clientSecret": "xxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "subscriptionId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "tenantId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "activeDirectoryEndpointUrl": "https://login.microsoftonline.com",
  "resourceManagerEndpointUrl": "https://management.azure.com/",
  "activeDirectoryGraphResourceId": "https://graph.windows.net/",
  "sqlManagementEndpointUrl": "https://management.core.windows.net:8443/",
  "galleryEndpointUrl": "https://gallery.azure.com/",
  "managementEndpointUrl": "https://management.core.windows.net/"
}
```

### 4. 配置 OIDC 聯合憑證（推薦）

使用 OIDC 更安全，不需要管理 secrets：

```bash
# 獲取應用程式物件 ID
APP_OBJECT_ID=$(az ad app list --display-name "${APP_NAME}" --query "[0].id" --output tsv)

# 為 main 分支創建聯合憑證
az ad app federated-credential create \
  --id ${APP_OBJECT_ID} \
  --parameters '{
    "name": "github-main",
    "issuer": "https://token.actions.githubusercontent.com",
    "subject": "repo:Cloudinfo-Github/call-center-ai:ref:refs/heads/main",
    "audiences": ["api://AzureADTokenExchange"]
  }'

# 為手動觸發創建聯合憑證
az ad app federated-credential create \
  --id ${APP_OBJECT_ID} \
  --parameters '{
    "name": "github-environment",
    "issuer": "https://token.actions.githubusercontent.com",
    "subject": "repo:Cloudinfo-Github/call-center-ai:environment:production",
    "audiences": ["api://AzureADTokenExchange"]
  }'
```

---

## 🔑 步驟二：配置 GitHub Secrets

### 1. 前往 GitHub 設定

在您的 GitHub 專案中：

```
Settings → Secrets and variables → Actions → New repository secret
```

### 2. 添加以下 Secrets

| Secret 名稱 | 值 | 說明 |
|------------|-----|------|
| `AZURE_CLIENT_ID` | 從步驟一取得的 `clientId` | 服務主體的客戶端 ID |
| `AZURE_TENANT_ID` | 從步驟一取得的 `tenantId` | Azure AD 租戶 ID |
| `AZURE_SUBSCRIPTION_ID` | 從步驟一取得的 `subscriptionId` | Azure 訂閱 ID |
| `AZURE_CLIENT_SECRET` | 從步驟一取得的 `clientSecret` | （可選，如使用 OIDC 則不需要）|

### 3. 驗證 Secrets

確保所有必要的 secrets 都已添加：

![GitHub Secrets](https://docs.github.com/assets/cb-28937/images/help/settings/actions-org-secrets-list.png)

---

## 🏗️ 步驟三：配置部署環境

### 1. 創建 GitHub Environments

在 GitHub 專案中創建環境：

```
Settings → Environments → New environment
```

建議創建以下環境：

#### Development 環境

- **名稱**: `development`
- **部署分支**: `main`, `develop`
- **審批**: 不需要
- **Environment secrets**:
  - 可選：覆寫特定環境的配置

#### Staging 環境

- **名稱**: `staging`
- **部署分支**: `main`
- **審批**: 可選
- **Environment secrets**:
  - 如有不同的訂閱或配置

#### Production 環境

- **名稱**: `production`
- **部署分支**: 僅 `main`
- **審批**: **必須** - 添加審批者
- **Environment secrets**:
  - 生產環境專用配置

### 2. 配置環境變數（可選）

在每個環境中，您可以設定：

| 變數名稱 | 值 | 說明 |
|---------|-----|------|
| `RESOURCE_GROUP_NAME` | `call-center-ai-dev` | 資源群組名稱 |
| `LOCATION` | `swedencentral` | Azure 區域 |

---

## 🚀 步驟四：測試部署

### 1. 手動觸發部署

前往 GitHub Actions：

```
Actions → Deploy to Azure → Run workflow
```

選擇：
- **環境**: `development`
- **資源群組**: `call-center-ai-dev`

點擊 **Run workflow**

### 2. 監控部署進度

在 Actions 頁面查看即時日誌：

```
https://github.com/Cloudinfo-Github/call-center-ai/actions
```

### 3. 驗證部署

部署完成後，檢查：

```bash
# 健康檢查
curl https://your-app-url.azurecontainerapps.io/health/liveness

# API 文檔
open https://your-app-url.azurecontainerapps.io/docs
```

---

## 🔄 步驟五：自動部署設定

### 自動觸發條件

workflow 會在以下情況自動觸發：

1. **推送到 main 分支**
   ```bash
   git push origin main
   ```

2. **創建版本標籤**
   ```bash
   git tag -a v1.0.0 -m "Release v1.0.0"
   git push origin v1.0.0
   ```

3. **Pipeline 成功建置後**
   - 當 `.github/workflows/pipeline.yaml` 成功完成
   - 自動觸發部署到 development 環境

### 禁用自動部署

如果您只想手動部署，編輯 `.github/workflows/deploy-azure.yaml`：

```yaml
on:
  # 註解掉自動觸發
  # push:
  #   branches:
  #     - main

  # 只保留手動觸發
  workflow_dispatch:
    inputs:
      environment:
        # ...
```

---

## 🎯 步驟六：Azure 資源配置

### 1. 準備配置檔案

創建或編輯 `config.yaml`：

```yaml
# 範例配置
conversation:
  initiate:
    bot_company: "您的公司名稱"
    bot_name: "AI 助理"
    agent_phone_number: "+886XXXXXXXXX"

communication_services:
  phone_number: "+886XXXXXXXXX"  # 您購買的 Azure 電話號碼

# 其他配置...
```

### 2. 配置 Azure 資源

部署後，您需要手動配置：

#### a. 購買電話號碼

```bash
# 在 Azure Portal 中
Communication Services → 電話號碼 → 購買
```

#### b. 配置 Communication Services

```bash
# 在 Azure Portal 中
Communication Services → 設定 → 事件訂閱
```

#### c. 設定 Application Insights

```bash
# 在 Azure Portal 中
Application Insights → 監控 → 設定告警
```

---

## 📊 步驟七：監控和日誌

### 查看應用程式日誌

```bash
# 使用 Azure CLI
az containerapp logs show \
  --name call-center-ai \
  --resource-group call-center-ai-dev \
  --follow \
  --format text \
  --tail 100
```

### 使用 Makefile

```bash
make logs name=call-center-ai-dev
```

### 在 Azure Portal 查看

```
Azure Portal → Container Apps → call-center-ai → 監控 → 日誌串流
```

---

## 🔧 故障排除

### 問題 1: 驗證失敗

**錯誤**: `AADSTS700016: Application not found`

**解決方案**:
- 確認 `AZURE_CLIENT_ID` 正確
- 確認服務主體已創建
- 檢查 OIDC 聯合憑證配置

### 問題 2: 權限不足

**錯誤**: `Authorization failed`

**解決方案**:
```bash
# 賦予服務主體貢獻者角色
az role assignment create \
  --assignee <CLIENT_ID> \
  --role Contributor \
  --scope /subscriptions/<SUBSCRIPTION_ID>
```

### 問題 3: 部署超時

**錯誤**: `Deployment timeout`

**解決方案**:
- 檢查 Azure 區域是否支援所有服務
- 增加 workflow 中的等待時間
- 檢查 Bicep 模板參數

### 問題 4: 健康檢查失敗

**錯誤**: `Health check failed`

**解決方案**:
```bash
# 檢查應用程式日誌
az containerapp logs show \
  --name call-center-ai \
  --resource-group <your-rg> \
  --tail 50

# 檢查環境變數
az containerapp show \
  --name call-center-ai \
  --resource-group <your-rg> \
  --query "properties.template.containers[0].env"
```

---

## 🎨 進階配置

### 多環境配置

為不同環境創建不同的配置：

```yaml
# config.development.yaml
conversation:
  initiate:
    bot_name: "AI 助理 (開發)"

# config.production.yaml
conversation:
  initiate:
    bot_name: "AI 助理"
```

### 自訂 Bicep 參數

編輯 `.github/workflows/deploy-azure.yaml`：

```yaml
- name: Deploy Bicep template
  run: |
    az deployment sub create \
      --parameters \
        llmFastModel=gpt-4o-realtime-preview \
        llmSlowModel=o3-mini \
        # ... 其他 2025 優化參數
```

### 部署通知

添加 Slack 或 Teams 通知：

```yaml
- name: Notify deployment
  if: always()
  uses: slackapi/slack-github-action@v1.25.0
  with:
    webhook-url: ${{ secrets.SLACK_WEBHOOK }}
    payload: |
      {
        "text": "部署 ${{ needs.setup.outputs.environment }}: ${{ job.status }}"
      }
```

---

## 📚 相關資源

- [Azure Container Apps 文檔](https://learn.microsoft.com/azure/container-apps/)
- [GitHub Actions 文檔](https://docs.github.com/actions)
- [Azure OIDC 配置](https://docs.github.com/actions/deployment/security-hardening-your-deployments/configuring-openid-connect-in-azure)
- [Bicep 文檔](https://learn.microsoft.com/azure/azure-resource-manager/bicep/)

---

## ✅ 檢查清單

部署前確認：

- [ ] Azure 服務主體已創建
- [ ] GitHub Secrets 已配置
- [ ] GitHub Environments 已設置
- [ ] OIDC 聯合憑證已配置（推薦）
- [ ] 配置檔案已準備
- [ ] Azure 電話號碼已購買（如需）
- [ ] 測試手動觸發部署成功
- [ ] 健康檢查通過
- [ ] 監控和告警已設置

---

**準備好了嗎？開始部署吧！🚀**

```bash
# 推送到 GitHub 觸發自動部署
git add .
git commit -m "feat: Add Azure deployment automation"
git push origin main
```
