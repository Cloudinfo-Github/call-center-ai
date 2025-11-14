# 🚀 架構現代化遷移指南

從當前架構遷移到 2025 最佳實踐的完整指南。

---

## 📋 遷移前檢查清單

### 環境準備

- [ ] **備份當前系統**
  ```bash
  # 備份配置
  cp config.yaml config.yaml.backup

  # 備份資料庫
  az cosmosdb database backup create \
    --resource-group <your-rg> \
    --account-name <your-account>
  ```

- [ ] **驗證 Azure 訂閱權限**
  - [ ] 有權限創建 Cosmos DB 容器
  - [ ] 有權限管理 Redis
  - [ ] 有權限存取 OpenAI 服務

- [ ] **準備測試環境**
  - [ ] 建立獨立的測試資源群組
  - [ ] 準備測試電話號碼
  - [ ] 設定監控和日誌

- [ ] **文檔和溝通**
  - [ ] 通知團隊成員遷移計畫
  - [ ] 準備回滾計畫
  - [ ] 設定維護時間窗口

---

## 🎯 遷移階段

### **階段一：基礎設施準備（第 1 週）**

#### 1.1 升級依賴

```bash
# 更新 pyproject.toml
```

新增/更新以下依賴：

```toml
[project.dependencies]
openai = ">= 1.60.0"  # 支援 Realtime API
orjson = "~= 3.10"    # JSON 加速
httpx = "~= 0.28"     # HTTP/2 支援
redis = { version = "~= 5.2", extras = ["hiredis"] }
prometheus-client = "~= 0.21"  # 監控指標
```

執行安裝：

```bash
uv sync --all-extras
```

#### 1.2 Cosmos DB 向量索引設定

創建遷移腳本：

```python
# scripts/migrate_cosmos_vector.py
import asyncio
from examples.cosmos_vector_search import CosmosVectorStore

async def migrate():
    store = CosmosVectorStore(
        endpoint=os.getenv("COSMOS_ENDPOINT"),
        key=os.getenv("COSMOS_KEY")
    )

    await store.initialize()
    print("✅ Cosmos DB 向量索引已啟用")

asyncio.run(migrate())
```

執行遷移：

```bash
python scripts/migrate_cosmos_vector.py
```

#### 1.3 Redis Stack 升級

如果使用 Azure Cache for Redis：

```bash
# 升級到 Redis 7.x (支援向量搜尋)
az redis update \
  --resource-group <your-rg> \
  --name <your-redis> \
  --sku Premium \
  --redis-version 7
```

如果自架 Redis：

```bash
docker run -d \
  --name redis-stack \
  -p 6379:6379 \
  redis/redis-stack:latest
```

#### 1.4 OpenAI 配置

在 Azure OpenAI Studio 中部署新模型：

```yaml
部署清單:
  - gpt-4o-realtime-preview (2024-12-17)
  - gpt-4o-transcribe
  - o3-mini (2025-01-31)
```

---

### **階段二：程式碼重構（第 2-3 週）**

#### 2.1 創建新模組結構

```bash
mkdir -p app/core/{voice,llm,rag,optimization}
mkdir -p app/services/{azure,openai,cache}
```

#### 2.2 整合 Realtime API

複製範例到專案：

```bash
cp examples/realtime_api_integration.py app/core/voice/realtime.py
```

修改整合到現有系統：

```python
# app/core/voice/realtime.py
from app.helpers.llm_tools import DefaultPlugin

class RealtimeVoiceAgent:
    def __init__(self, config, plugin: DefaultPlugin):
        self.plugin = plugin
        # ... 其他初始化

    async def _execute_tool(self, function_name, arguments):
        """整合現有工具系統"""
        return await getattr(self.plugin, function_name)(**arguments)
```

#### 2.3 實施智能路由

創建路由邏輯：

```python
# app/core/voice/router.py
from typing import Literal

RouteStrategy = Literal["realtime", "traditional", "smart"]

class VoiceRouter:
    def __init__(
        self,
        realtime_handler,
        traditional_handler,
        strategy: RouteStrategy = "smart"
    ):
        self.realtime = realtime_handler
        self.traditional = traditional_handler
        self.strategy = strategy

    async def route_call(self, call_context):
        if self.strategy == "smart":
            # 智能選擇
            if call_context.requires_low_latency:
                return await self.realtime.handle(call_context)
            else:
                return await self.traditional.handle(call_context)

        elif self.strategy == "realtime":
            return await self.realtime.handle(call_context)

        else:
            return await self.traditional.handle(call_context)
```

#### 2.4 整合 Cosmos DB 向量搜尋

```bash
cp examples/cosmos_vector_search.py app/persistence/cosmos_vector.py
```

更新 RAG 管道：

```python
# app/helpers/call_llm.py 中的 RAG 整合

from app.persistence.cosmos_vector import CosmosVectorStore, HybridRAGEngine

# 替換現有的 AI Search
rag_engine = HybridRAGEngine(
    cosmos_store=cosmos_vector_store,
    redis_cache=redis_vector_cache
)

# 在 LLM 處理前查詢
async def get_context(query):
    embedding = await get_embedding(query)
    results = await rag_engine.search(embedding, top_k=5)
    return [r.content for r in results]
```

---

### **階段三：A/B 測試部署（第 4 週）**

#### 3.1 實施 A/B 測試框架

```python
# app/core/experiments/ab_test.py
import hashlib

class ABTest:
    def __init__(self, test_name: str, variants: dict):
        self.test_name = test_name
        self.variants = variants  # {"A": 0.5, "B": 0.5}

    def get_variant(self, user_id: str) -> str:
        """根據 user_id 穩定分配變體"""
        hash_value = int(
            hashlib.md5(f"{self.test_name}:{user_id}".encode()).hexdigest(),
            16
        )
        ratio = (hash_value % 100) / 100

        cumulative = 0
        for variant, weight in self.variants.items():
            cumulative += weight
            if ratio < cumulative:
                return variant

        return list(self.variants.keys())[0]

# 使用
ab_test = ABTest(
    test_name="realtime_vs_traditional",
    variants={"realtime": 0.3, "traditional": 0.7}
)

variant = ab_test.get_variant(call_id)
if variant == "realtime":
    handler = realtime_handler
else:
    handler = traditional_handler
```

#### 3.2 配置監控

```python
# app/core/monitoring/metrics.py
from prometheus_client import Histogram, Counter, Gauge

# 延遲指標
latency_histogram = Histogram(
    'call_latency_seconds',
    'Call latency distribution',
    ['variant', 'stage']
)

# 成本指標
cost_gauge = Gauge(
    'call_cost_dollars',
    'Cost per call',
    ['variant']
)

# 品質指標
completion_rate = Gauge(
    'call_completion_rate',
    'Successful completion rate',
    ['variant']
)
```

#### 3.3 逐步推廣

```yaml
# Week 1: 30% Realtime
variants:
  realtime: 0.3
  traditional: 0.7

# Week 2: 50% Realtime (如果指標良好)
variants:
  realtime: 0.5
  traditional: 0.5

# Week 3: 70% Realtime
variants:
  realtime: 0.7
  traditional: 0.3

# Week 4: 100% Realtime
variants:
  realtime: 1.0
```

---

### **階段四：優化和穩定（第 5-6 週）**

#### 4.1 效能調優

**資料庫連接池優化：**

```python
# app/persistence/cosmos_db.py
from azure.cosmos.aio import CosmosClient

client = CosmosClient(
    url=config.endpoint,
    credential=config.key,
    connection_pool_size=20,  # 增加連接池
    connection_timeout=30,
    request_timeout=10
)
```

**Redis 連接池優化：**

```python
# app/persistence/redis.py
import redis.asyncio as redis

pool = redis.ConnectionPool(
    host=config.host,
    port=config.port,
    max_connections=50,  # 增加最大連接數
    socket_timeout=5,
    socket_keepalive=True,
    decode_responses=True
)
```

**FastAPI 優化：**

```python
# app/main.py
from fastapi import FastAPI
from fastapi.responses import ORJSONResponse

app = FastAPI(
    default_response_class=ORJSONResponse,  # 使用 orjson
    docs_url="/docs" if config.env == "dev" else None
)

# 添加中介軟體
@app.middleware("http")
async def add_process_time_header(request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response
```

#### 4.2 快取策略優化

```python
# app/helpers/cache.py
from functools import wraps
import hashlib

def cache_embeddings(ttl=3600):
    """快取 embedding 結果"""
    def decorator(func):
        @wraps(func)
        async def wrapper(text: str, *args, **kwargs):
            # 生成快取鍵
            cache_key = f"emb:{hashlib.md5(text.encode()).hexdigest()}"

            # 查詢快取
            cached = await redis_client.get(cache_key)
            if cached:
                return json.loads(cached)

            # 計算並快取
            result = await func(text, *args, **kwargs)
            await redis_client.setex(
                cache_key,
                ttl,
                json.dumps(result)
            )
            return result
        return wrapper
    return decorator

@cache_embeddings(ttl=86400)  # 快取 24 小時
async def get_embedding(text: str):
    # ... OpenAI API 調用
    pass
```

---

## 🧪 測試計畫

### 單元測試

```python
# tests/test_realtime_integration.py
import pytest
from app.core.voice.realtime import RealtimeVoiceAgent

@pytest.mark.asyncio
async def test_realtime_session():
    agent = RealtimeVoiceAgent(
        api_key="test-key",
        model="gpt-4o-realtime-preview"
    )

    async def mock_audio_stream():
        yield b'\x00' * 1024

    events = []
    async for event in agent.start_session(mock_audio_stream()):
        events.append(event)

    assert len(events) > 0
```

### 整合測試

```python
# tests/test_cosmos_vector.py
import pytest
from app.persistence.cosmos_vector import CosmosVectorStore

@pytest.mark.asyncio
async def test_vector_search():
    store = CosmosVectorStore(
        endpoint=os.getenv("TEST_COSMOS_ENDPOINT"),
        key=os.getenv("TEST_COSMOS_KEY")
    )

    await store.initialize()

    # 添加測試文檔
    await store.add_document(
        doc_id="test-001",
        content="測試內容",
        embedding=[0.1] * 3072,
        category="test"
    )

    # 搜尋
    results = await store.vector_search(
        query_embedding=[0.1] * 3072,
        top_k=1
    )

    assert len(results) == 1
    assert results[0].id == "test-001"
```

### 負載測試

```python
# tests/load_test.py
from locust import HttpUser, task, between

class CallCenterUser(HttpUser):
    wait_time = between(1, 3)

    @task
    def initiate_call(self):
        self.client.post("/call", json={
            "phone_number": "+1234567890",
            "initiate": {
                "bot_name": "Test Bot"
            }
        })

    @task(3)
    def get_call_status(self):
        self.client.get("/call")
```

執行負載測試：

```bash
locust -f tests/load_test.py --host http://localhost:8080
```

---

## 📊 監控和驗證

### 關鍵指標

建立監控儀表板追蹤以下指標：

| 指標 | 目標 | 告警閾值 |
|------|------|----------|
| P50 延遲 | < 250ms | > 400ms |
| P95 延遲 | < 400ms | > 600ms |
| P99 延遲 | < 600ms | > 1000ms |
| 完成率 | > 95% | < 90% |
| 錯誤率 | < 0.1% | > 1% |
| 成本/通話 | < $0.15 | > $0.25 |

### Application Insights 查詢

```kusto
// 延遲分佈
customMetrics
| where name == "call_latency_seconds"
| extend variant = tostring(customDimensions.variant)
| summarize
    p50=percentile(value, 50),
    p95=percentile(value, 95),
    p99=percentile(value, 99)
    by variant
| render timechart

// 成本比較
customMetrics
| where name == "call_cost_dollars"
| extend variant = tostring(customDimensions.variant)
| summarize avg_cost=avg(value) by variant
| render columnchart

// 錯誤率
requests
| where success == false
| extend variant = tostring(customDimensions.variant)
| summarize error_rate=count() by variant, bin(timestamp, 1h)
| render timechart
```

---

## 🔄 回滾計畫

如果遷移遇到問題，執行以下步驟回滾：

### 1. 切換回傳統架構

```python
# config.yaml
voice:
  routing:
    strategy: traditional  # 強制使用傳統管道
```

### 2. 恢復配置

```bash
cp config.yaml.backup config.yaml
```

### 3. 重新部署

```bash
make deploy name=<your-resource-group>
```

### 4. 驗證

```bash
# 執行健康檢查
curl http://your-app/health/readiness

# 檢查日誌
make logs name=<your-resource-group>
```

---

## ✅ 遷移完成檢查清單

- [ ] **效能驗證**
  - [ ] P50 延遲 < 250ms
  - [ ] P95 延遲 < 400ms
  - [ ] P99 延遲 < 600ms

- [ ] **成本驗證**
  - [ ] 每通電話成本 < $0.15
  - [ ] 月度總成本降低

- [ ] **品質驗證**
  - [ ] 完成率 > 95%
  - [ ] 轉接率 < 5%
  - [ ] 錯誤率 < 0.1%

- [ ] **文檔更新**
  - [ ] 更新 README.md
  - [ ] 更新部署文檔
  - [ ] 更新運維手冊

- [ ] **團隊培訓**
  - [ ] 開發團隊了解新架構
  - [ ] 運維團隊了解監控指標
  - [ ] 準備故障排除指南

- [ ] **清理**
  - [ ] 移除舊的 AI Search 資源
  - [ ] 清理測試資源
  - [ ] 歸檔備份

---

## 🆘 故障排除

### 常見問題

#### 1. Realtime API 連接失敗

```python
# 錯誤: WebSocket connection failed
# 解決方案: 檢查網路配置和防火牆規則

# 驗證連接
import websockets

async def test_connection():
    async with websockets.connect(
        "wss://api.openai.com/v1/realtime",
        extra_headers={"Authorization": f"Bearer {api_key}"}
    ) as ws:
        print("連接成功")
```

#### 2. Cosmos DB 向量索引未生效

```bash
# 檢查容器配置
az cosmosdb sql container show \
  --resource-group <rg> \
  --account-name <account> \
  --database-name call_center_ai \
  --name knowledge_base \
  --query 'resource.vectorEmbeddingPolicy'
```

#### 3. Redis 記憶體不足

```bash
# 檢查 Redis 記憶體使用
redis-cli INFO memory

# 調整淘汰策略
redis-cli CONFIG SET maxmemory-policy allkeys-lru
```

---

## 📞 支援

如遇問題，請：

1. 查看 [GitHub Issues](https://github.com/microsoft/call-center-ai/issues)
2. 聯繫團隊支援
3. 參考 Azure 文檔

---

**祝遷移順利！🚀**
