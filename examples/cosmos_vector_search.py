"""
Cosmos DB 向量搜尋實作範例
2025 年架構優化 - 使用原生向量索引替代 AI Search

優勢:
- 延遲 < 20ms (vs AI Search ~50-100ms)
- 成本比 Pinecone 低 43 倍
- 統一資料庫（無需分離的搜尋服務）
- DiskANN 演算法（微軟研究院開發）
"""

import asyncio
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from azure.cosmos.aio import CosmosClient
from azure.cosmos import PartitionKey
import structlog

logger = structlog.get_logger()


@dataclass
class VectorSearchResult:
    """向量搜尋結果"""
    id: str
    content: str
    similarity: float
    metadata: Dict[str, Any]


class CosmosVectorStore:
    """
    Cosmos DB 向量儲存庫 (2025 新功能)

    使用 DiskANN 演算法實現高效向量搜尋
    """

    def __init__(
        self,
        endpoint: str,
        key: str,
        database_name: str = "call_center_ai",
        container_name: str = "knowledge_base",
        embedding_dimensions: int = 3072  # text-embedding-3-large
    ):
        self.client = CosmosClient(endpoint, key)
        self.database_name = database_name
        self.container_name = container_name
        self.embedding_dimensions = embedding_dimensions

        self.database = None
        self.container = None

    async def initialize(self):
        """初始化資料庫和容器"""
        logger.info("initializing_cosmos_vector_store")

        # 創建或獲取資料庫
        self.database = await self.client.create_database_if_not_exists(
            id=self.database_name
        )
        logger.info("database_ready", database=self.database_name)

        # 創建或獲取容器（啟用向量索引）
        await self._create_vector_enabled_container()

        logger.info("cosmos_vector_store_initialized")

    async def _create_vector_enabled_container(self):
        """創建啟用向量索引的容器"""

        # 容器配置
        container_config = {
            "id": self.container_name,
            "partition_key": PartitionKey(path="/category"),

            # 🆕 向量索引策略 (2025)
            "indexing_policy": {
                "automatic": True,
                "indexing_mode": "consistent",

                # 包含路徑
                "included_paths": [
                    {"path": "/*"}
                ],

                # 向量索引
                "vector_indexes": [
                    {
                        "path": "/embedding",
                        "type": "diskANN",  # 微軟 DiskANN 演算法
                        "dimensions": self.embedding_dimensions,
                        "distanceFunction": "cosine",

                        # DiskANN 參數
                        "quantization": {
                            "type": "scalar",
                            "bits": 8  # 量化以節省儲存空間
                        }
                    }
                ]
            },

            # 向量嵌入策略
            "vector_embedding_policy": {
                "vector_embeddings": [
                    {
                        "path": "/embedding",
                        "dataType": "float32",
                        "dimensions": self.embedding_dimensions,
                        "distanceFunction": "cosine"
                    }
                ]
            }
        }

        # 建立容器
        try:
            self.container = await self.database.create_container_if_not_exists(
                **container_config,
                offer_throughput=4000  # 自動擴展 RU
            )
            logger.info(
                "container_created",
                container=self.container_name,
                vector_enabled=True
            )
        except Exception as e:
            logger.error("container_creation_error", error=str(e))
            raise

    async def add_document(
        self,
        doc_id: str,
        content: str,
        embedding: List[float],
        category: str = "general",
        metadata: Dict[str, Any] = None
    ):
        """
        添加文檔和向量

        Args:
            doc_id: 文檔 ID
            content: 文本內容
            embedding: 向量嵌入 (3072 維)
            category: 分類 (分區鍵)
            metadata: 其他元數據
        """
        document = {
            "id": doc_id,
            "content": content,
            "embedding": embedding,  # 向量欄位
            "category": category,
            "metadata": metadata or {},
        }

        try:
            await self.container.create_item(body=document)
            logger.info(
                "document_added",
                doc_id=doc_id,
                category=category,
                embedding_dims=len(embedding)
            )
        except Exception as e:
            logger.error(
                "document_add_error",
                doc_id=doc_id,
                error=str(e)
            )
            raise

    async def vector_search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        category: Optional[str] = None,
        min_similarity: float = 0.7
    ) -> List[VectorSearchResult]:
        """
        向量相似度搜尋

        Args:
            query_embedding: 查詢向量
            top_k: 返回前 K 個結果
            category: 可選的分類過濾
            min_similarity: 最小相似度閾值

        Returns:
            搜尋結果列表
        """
        logger.info(
            "vector_search_started",
            top_k=top_k,
            category=category
        )

        # 構建查詢
        if category:
            # 帶分類過濾的查詢
            query = """
            SELECT TOP @top_k
                c.id,
                c.content,
                c.metadata,
                VectorDistance(c.embedding, @embedding) AS similarity
            FROM c
            WHERE c.category = @category
                AND VectorDistance(c.embedding, @embedding) < @max_distance
            ORDER BY VectorDistance(c.embedding, @embedding)
            """
            parameters = [
                {"name": "@embedding", "value": query_embedding},
                {"name": "@top_k", "value": top_k},
                {"name": "@category", "value": category},
                {"name": "@max_distance", "value": 1 - min_similarity}
            ]
        else:
            # 全局搜尋
            query = """
            SELECT TOP @top_k
                c.id,
                c.content,
                c.metadata,
                VectorDistance(c.embedding, @embedding) AS similarity
            FROM c
            WHERE VectorDistance(c.embedding, @embedding) < @max_distance
            ORDER BY VectorDistance(c.embedding, @embedding)
            """
            parameters = [
                {"name": "@embedding", "value": query_embedding},
                {"name": "@top_k", "value": top_k},
                {"name": "@max_distance", "value": 1 - min_similarity}
            ]

        # 執行查詢
        results = []
        try:
            items = self.container.query_items(
                query=query,
                parameters=parameters,
                enable_cross_partition_query=True
            )

            async for item in items:
                results.append(VectorSearchResult(
                    id=item["id"],
                    content=item["content"],
                    similarity=1 - item["similarity"],  # 轉換為相似度
                    metadata=item.get("metadata", {})
                ))

            logger.info(
                "vector_search_completed",
                results_count=len(results),
                avg_similarity=sum(r.similarity for r in results) / len(results) if results else 0
            )

        except Exception as e:
            logger.error("vector_search_error", error=str(e))
            raise

        return results

    async def hybrid_search(
        self,
        query_text: str,
        query_embedding: List[float],
        top_k: int = 5,
        text_weight: float = 0.3,
        vector_weight: float = 0.7
    ) -> List[VectorSearchResult]:
        """
        混合搜尋（結合關鍵字和向量）

        Args:
            query_text: 查詢文本（用於關鍵字搜尋）
            query_embedding: 查詢向量
            top_k: 返回結果數
            text_weight: 文本搜尋權重
            vector_weight: 向量搜尋權重

        Returns:
            混合搜尋結果
        """
        query = """
        SELECT TOP @top_k
            c.id,
            c.content,
            c.metadata,
            (
                (@text_weight * RANK(FullTextScore(c.content, [@query_text]))) +
                (@vector_weight * (1 - VectorDistance(c.embedding, @embedding)))
            ) AS hybrid_score
        FROM c
        ORDER BY hybrid_score DESC
        """

        parameters = [
            {"name": "@top_k", "value": top_k},
            {"name": "@query_text", "value": query_text},
            {"name": "@embedding", "value": query_embedding},
            {"name": "@text_weight", "value": text_weight},
            {"name": "@vector_weight", "value": vector_weight}
        ]

        results = []
        try:
            items = self.container.query_items(
                query=query,
                parameters=parameters,
                enable_cross_partition_query=True
            )

            async for item in items:
                results.append(VectorSearchResult(
                    id=item["id"],
                    content=item["content"],
                    similarity=item["hybrid_score"],
                    metadata=item.get("metadata", {})
                ))

            logger.info(
                "hybrid_search_completed",
                results_count=len(results)
            )

        except Exception as e:
            logger.error("hybrid_search_error", error=str(e))
            raise

        return results

    async def close(self):
        """關閉連接"""
        await self.client.close()


class HybridRAGEngine:
    """
    混合 RAG 引擎
    結合 Redis (熱快取) 和 Cosmos DB (完整資料集)
    """

    def __init__(
        self,
        cosmos_store: CosmosVectorStore,
        redis_cache: Optional[Any] = None  # RedisVectorCache
    ):
        self.cosmos = cosmos_store
        self.redis = redis_cache

    async def search(
        self,
        query_embedding: List[float],
        top_k: int = 5
    ) -> List[VectorSearchResult]:
        """
        智能搜尋策略

        1. 先查 Redis (熱快取) - < 5ms
        2. 未命中則查 Cosmos DB - < 20ms
        3. 自動提升熱門結果到 Redis
        """
        results = []

        # 1. 嘗試 Redis 快取
        if self.redis:
            try:
                cache_results = await self.redis.search(
                    query_embedding,
                    k=top_k
                )
                if cache_results:
                    logger.info("cache_hit", count=len(cache_results))
                    return cache_results
            except Exception as e:
                logger.warning("cache_miss", error=str(e))

        # 2. 查詢 Cosmos DB
        results = await self.cosmos.vector_search(
            query_embedding,
            top_k=top_k
        )

        # 3. 提升到熱快取
        if self.redis and results:
            await self._promote_to_cache(results)

        return results

    async def _promote_to_cache(self, results: List[VectorSearchResult]):
        """提升結果到 Redis 快取"""
        if not self.redis:
            return

        try:
            for result in results:
                await self.redis.add(
                    doc_id=result.id,
                    content=result.content,
                    embedding=result.metadata.get("embedding"),
                    ttl=3600  # 1 小時
                )
            logger.info("promoted_to_cache", count=len(results))
        except Exception as e:
            logger.error("cache_promotion_error", error=str(e))


# 使用範例
async def example_usage():
    """範例：如何使用 Cosmos DB 向量搜尋"""

    # 1. 初始化
    store = CosmosVectorStore(
        endpoint="https://your-account.documents.azure.com:443/",
        key="your-key",
        database_name="call_center_ai",
        container_name="knowledge_base"
    )

    await store.initialize()

    # 2. 添加文檔（通常在離線處理中完成）
    sample_embedding = [0.1] * 3072  # 模擬 embedding

    await store.add_document(
        doc_id="doc-001",
        content="保險理賠流程：首先聯繫客服，提供事故詳細資訊...",
        embedding=sample_embedding,
        category="insurance_claims",
        metadata={
            "source": "knowledge_base",
            "last_updated": "2025-01-01"
        }
    )

    # 3. 向量搜尋
    query_embedding = [0.15] * 3072  # 模擬查詢向量

    results = await store.vector_search(
        query_embedding=query_embedding,
        top_k=5,
        category="insurance_claims",
        min_similarity=0.7
    )

    # 4. 處理結果
    for i, result in enumerate(results, 1):
        print(f"\n結果 {i}:")
        print(f"  相似度: {result.similarity:.3f}")
        print(f"  內容: {result.content[:100]}...")

    # 5. 混合搜尋
    hybrid_results = await store.hybrid_search(
        query_text="如何申請理賠",
        query_embedding=query_embedding,
        top_k=5
    )

    # 清理
    await store.close()


if __name__ == "__main__":
    asyncio.run(example_usage())
