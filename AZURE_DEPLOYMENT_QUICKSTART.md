# 🚀 Azure 自動部署快速開始

10 分鐘內完成從零到部署！

---

## 📋 前置要求

確保您已安裝：
- [Azure CLI](https://docs.microsoft.com/cli/azure/install-azure-cli)
- [Git](https://git-scm.com/downloads)
- [GitHub CLI](https://cli.github.com/)（可選，但推薦）

---

## ⚡ 快速設置（3 步驟）

### 步驟 1: 執行自動設置腳本

```bash
# 克隆專案（如果還沒有）
git clone https://github.com/Cloudinfo-Github/call-center-ai.git
cd call-center-ai

# 執行設置腳本
./scripts/setup_azure_deployment.sh
```

腳本會自動：
- ✅ 登入 Azure
- ✅ 創建服務主體
- ✅ 配置 OIDC 認證
- ✅ 設定 GitHub Secrets（如果安裝了 GitHub CLI）

### 步驟 2: 手動設定 GitHub Secrets（如未使用 GitHub CLI）

前往 GitHub 設定：
```
https://github.com/Cloudinfo-Github/call-center-ai/settings/secrets/actions
```

添加以下 secrets（從腳本輸出中複製）：
- `AZURE_CLIENT_ID`
- `AZURE_TENANT_ID`
- `AZURE_SUBSCRIPTION_ID`

### 步驟 3: 觸發部署

#### 選項 A: 使用 GitHub UI

1. 前往 [GitHub Actions](https://github.com/Cloudinfo-Github/call-center-ai/actions)
2. 選擇 **"Deploy to Azure"** workflow
3. 點擊 **"Run workflow"**
4. 選擇環境和資源群組
5. 點擊 **"Run workflow"**

#### 選項 B: 使用命令行

```bash
# 推送到 main 分支自動觸發
git push origin main
```

---

## 🎯 第一次部署

建議的第一次部署設定：

| 參數 | 值 | 說明 |
|------|-----|------|
| **環境** | `development` | 開發環境 |
| **資源群組** | `call-center-ai-dev` | Azure 資源群組名稱 |

部署時間：約 10-15 分鐘

---

## 📊 監控部署進度

### 1. 在 GitHub 查看

前往 [Actions 頁面](https://github.com/Cloudinfo-Github/call-center-ai/actions)

您會看到：
- ✅ Setup Deployment
- ✅ Deploy Infrastructure
- ✅ Deploy Static Assets
- ✅ Deploy Config
- ✅ Health Check
- ✅ Deployment Summary

### 2. 在 Azure 查看

```bash
# 使用 Azure CLI
az group list --query "[?name=='call-center-ai-dev']" --output table

# 查看容器應用
az containerapp list \
  --resource-group call-center-ai-dev \
  --output table
```

---

## 🔍 部署完成後

### 1. 獲取應用程式 URL

從 GitHub Actions 部署摘要中複製，或使用命令：

```bash
az containerapp show \
  --name call-center-ai \
  --resource-group call-center-ai-dev \
  --query "properties.configuration.ingress.fqdn" \
  --output tsv
```

### 2. 驗證部署

```bash
# 健康檢查
curl https://your-app-url.azurecontainerapps.io/health/liveness

# 應該返回
{"status":"ok"}
```

### 3. 訪問 API 文檔

```
https://your-app-url.azurecontainerapps.io/docs
```

---

## 🎨 多環境部署

### Development（開發）

```yaml
環境: development
資源群組: call-center-ai-dev
自動部署: ✅ 每次推送到 main
審批需求: ❌
```

### Staging（預發布）

```yaml
環境: staging
資源群組: call-center-ai-staging
自動部署: ❌ 手動觸發
審批需求: ✅ 推薦
```

### Production（生產）

```yaml
環境: production
資源群組: call-center-ai-prod
自動部署: ❌ 僅標籤觸發
審批需求: ✅ 必須
```

設定 GitHub Environments：
```
Settings → Environments → New environment
```

---

## 🔧 常見問題

### Q1: 健康檢查失敗

**解決方案：**
```bash
# 查看應用程式日誌
az containerapp logs show \
  --name call-center-ai \
  --resource-group call-center-ai-dev \
  --follow \
  --tail 50
```

### Q2: 部署卡住

**解決方案：**
- 檢查 Azure 訂閱配額
- 確認所選區域支援所有服務
- 查看 GitHub Actions 日誌

### Q3: 找不到應用程式

**解決方案：**
```bash
# 列出所有容器應用
az containerapp list \
  --resource-group call-center-ai-dev \
  --output table

# 檢查部署狀態
az deployment sub show \
  --name call-center-ai-dev \
  --query "properties.provisioningState"
```

---

## 📚 下一步

### 1. 配置應用程式

編輯 `config.yaml`：
```yaml
conversation:
  initiate:
    bot_company: "您的公司名稱"
    bot_name: "AI 助理"
```

### 2. 設定監控

```bash
# 設定告警
az monitor metrics alert create \
  --name high-latency \
  --resource-group call-center-ai-dev \
  --condition "avg Latency > 1000"
```

### 3. 開始開發

查看完整的優化方案：
- [OPTIMIZATION_SUMMARY.md](OPTIMIZATION_SUMMARY.md) - 完整優化方案
- [ARCHITECTURE_2025.md](ARCHITECTURE_2025.md) - 架構設計
- [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md) - 遷移指南

---

## 🆘 需要幫助？

### 詳細文檔
- [完整部署設置指南](docs/AZURE_DEPLOYMENT_SETUP.md)
- [Azure 文檔](https://learn.microsoft.com/azure/container-apps/)

### 查看日誌
```bash
# 即時日誌
make logs name=call-center-ai-dev

# 或使用 Azure CLI
az containerapp logs show \
  --name call-center-ai \
  --resource-group call-center-ai-dev \
  --follow
```

### 聯繫支援
- GitHub Issues: https://github.com/Cloudinfo-Github/call-center-ai/issues
- 團隊支援: samuel_c@cloudinfo.com.tw

---

## ✅ 部署檢查清單

完成以下步驟：

- [ ] Azure CLI 已安裝並登入
- [ ] 執行 `./scripts/setup_azure_deployment.sh`
- [ ] GitHub Secrets 已配置
- [ ] 第一次手動部署成功
- [ ] 健康檢查通過
- [ ] 可以訪問 API 文檔
- [ ] 已設定監控和告警
- [ ] 配置檔案已更新

---

**恭喜！您的 Call Center AI 已經部署到 Azure！🎉**

現在可以開始使用 2025 最新架構的 AI 呼叫中心了！

```bash
# 查看應用狀態
curl https://your-app-url.azurecontainerapps.io/health/readiness

# 開始優化
# 參考 MIGRATION_GUIDE.md 開始遷移到新架構
```
