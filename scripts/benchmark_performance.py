"""
效能基準測試腳本

用於比較當前架構 vs 2025 優化架構的效能差異
"""

import asyncio
import time
from dataclasses import dataclass
from typing import List, Dict, Any
import statistics
import json
from datetime import datetime
import structlog

logger = structlog.get_logger()


@dataclass
class BenchmarkResult:
    """基準測試結果"""
    test_name: str
    architecture: str  # "current" or "optimized"
    latency_p50: float
    latency_p95: float
    latency_p99: float
    avg_latency: float
    min_latency: float
    max_latency: float
    throughput: float  # requests per second
    error_rate: float
    cost_per_call: float


class PerformanceBenchmark:
    """效能基準測試"""

    def __init__(self):
        self.results: List[BenchmarkResult] = []

    async def benchmark_latency(
        self,
        handler: callable,
        test_name: str,
        architecture: str,
        num_calls: int = 100
    ) -> BenchmarkResult:
        """
        基準測試延遲

        Args:
            handler: 通話處理函數
            test_name: 測試名稱
            architecture: 架構類型
            num_calls: 測試通話數量

        Returns:
            基準測試結果
        """
        logger.info(
            "starting_benchmark",
            test=test_name,
            arch=architecture,
            calls=num_calls
        )

        latencies = []
        errors = 0
        start_time = time.time()

        for i in range(num_calls):
            call_start = time.time()

            try:
                await handler(call_id=f"test-{i}")
                latency = (time.time() - call_start) * 1000  # ms
                latencies.append(latency)

            except Exception as e:
                errors += 1
                logger.error("call_failed", error=str(e), call_id=i)

            # 避免過載
            if i % 10 == 0:
                await asyncio.sleep(0.1)

        total_time = time.time() - start_time

        # 計算統計
        latencies.sort()
        result = BenchmarkResult(
            test_name=test_name,
            architecture=architecture,
            latency_p50=self._percentile(latencies, 50),
            latency_p95=self._percentile(latencies, 95),
            latency_p99=self._percentile(latencies, 99),
            avg_latency=statistics.mean(latencies) if latencies else 0,
            min_latency=min(latencies) if latencies else 0,
            max_latency=max(latencies) if latencies else 0,
            throughput=num_calls / total_time,
            error_rate=errors / num_calls,
            cost_per_call=self._estimate_cost(architecture)
        )

        self.results.append(result)

        logger.info(
            "benchmark_completed",
            test=test_name,
            arch=architecture,
            p50=f"{result.latency_p50:.2f}ms",
            p95=f"{result.latency_p95:.2f}ms",
            throughput=f"{result.throughput:.2f} req/s"
        )

        return result

    def _percentile(self, data: List[float], percentile: int) -> float:
        """計算百分位數"""
        if not data:
            return 0.0
        size = len(data)
        index = (size * percentile) // 100
        return data[min(index, size - 1)]

    def _estimate_cost(self, architecture: str) -> float:
        """估算每通電話成本"""
        if architecture == "current":
            # 當前架構成本估算
            return (
                0.005 +   # STT (gpt-4o-transcribe)
                0.08 +    # LLM (gpt-4o-nano, ~1000 tokens)
                0.005 +   # TTS (Azure Neural)
                0.01      # 其他服務 (Cosmos, Redis, etc.)
            )
        else:  # optimized
            # 優化架構成本估算
            return (
                0.10 +    # Realtime API (端到端)
                0.005     # 其他服務 (成本降低)
            )

    def compare_results(self) -> Dict[str, Any]:
        """比較不同架構的結果"""
        comparison = {
            "timestamp": datetime.now().isoformat(),
            "architectures": {},
            "improvements": {}
        }

        # 按架構分組
        by_arch = {}
        for result in self.results:
            if result.architecture not in by_arch:
                by_arch[result.architecture] = []
            by_arch[result.architecture].append(result)

        # 計算平均值
        for arch, results in by_arch.items():
            comparison["architectures"][arch] = {
                "avg_latency_p50": statistics.mean([r.latency_p50 for r in results]),
                "avg_latency_p95": statistics.mean([r.latency_p95 for r in results]),
                "avg_latency_p99": statistics.mean([r.latency_p99 for r in results]),
                "avg_throughput": statistics.mean([r.throughput for r in results]),
                "avg_error_rate": statistics.mean([r.error_rate for r in results]),
                "avg_cost_per_call": statistics.mean([r.cost_per_call for r in results])
            }

        # 計算改進百分比
        if "current" in comparison["architectures"] and "optimized" in comparison["architectures"]:
            current = comparison["architectures"]["current"]
            optimized = comparison["architectures"]["optimized"]

            comparison["improvements"] = {
                "latency_p50_reduction": self._calc_improvement(
                    current["avg_latency_p50"],
                    optimized["avg_latency_p50"]
                ),
                "latency_p95_reduction": self._calc_improvement(
                    current["avg_latency_p95"],
                    optimized["avg_latency_p95"]
                ),
                "latency_p99_reduction": self._calc_improvement(
                    current["avg_latency_p99"],
                    optimized["avg_latency_p99"]
                ),
                "throughput_increase": self._calc_improvement(
                    optimized["avg_throughput"],
                    current["avg_throughput"],
                    inverse=True
                ),
                "cost_reduction": self._calc_improvement(
                    current["avg_cost_per_call"],
                    optimized["avg_cost_per_call"]
                )
            }

        return comparison

    def _calc_improvement(
        self,
        before: float,
        after: float,
        inverse: bool = False
    ) -> float:
        """計算改進百分比"""
        if before == 0:
            return 0.0

        if inverse:
            # 對於吞吐量等指標（數值越高越好）
            return ((after - before) / before) * 100
        else:
            # 對於延遲、成本等指標（數值越低越好）
            return ((before - after) / before) * 100

    def generate_report(self, output_file: str = "benchmark_report.json"):
        """生成報告"""
        comparison = self.compare_results()

        # 控制台輸出
        print("\n" + "=" * 80)
        print("📊 效能基準測試報告")
        print("=" * 80)

        for arch, metrics in comparison["architectures"].items():
            print(f"\n🏗️  {arch.upper()} 架構:")
            print(f"  • P50 延遲: {metrics['avg_latency_p50']:.2f}ms")
            print(f"  • P95 延遲: {metrics['avg_latency_p95']:.2f}ms")
            print(f"  • P99 延遲: {metrics['avg_latency_p99']:.2f}ms")
            print(f"  • 吞吐量: {metrics['avg_throughput']:.2f} req/s")
            print(f"  • 錯誤率: {metrics['avg_error_rate']*100:.2f}%")
            print(f"  • 每通成本: ${metrics['avg_cost_per_call']:.4f}")

        if comparison["improvements"]:
            print("\n📈 改進指標:")
            improvements = comparison["improvements"]
            print(f"  • P50 延遲降低: {improvements['latency_p50_reduction']:.1f}%")
            print(f"  • P95 延遲降低: {improvements['latency_p95_reduction']:.1f}%")
            print(f"  • P99 延遲降低: {improvements['latency_p99_reduction']:.1f}%")
            print(f"  • 吞吐量提升: {improvements['throughput_increase']:.1f}%")
            print(f"  • 成本降低: {improvements['cost_reduction']:.1f}%")

        print("\n" + "=" * 80)

        # 輸出 JSON 檔案
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(comparison, f, indent=2, ensure_ascii=False)

        logger.info("report_generated", file=output_file)


# 測試處理器（模擬）
async def mock_current_handler(call_id: str):
    """模擬當前架構的通話處理"""
    # 模擬延遲
    await asyncio.sleep(0.5 + (time.time() % 0.5))  # 500-1000ms


async def mock_optimized_handler(call_id: str):
    """模擬優化架構的通話處理"""
    # 模擬延遲
    await asyncio.sleep(0.2 + (time.time() % 0.1))  # 200-300ms


# 主測試函數
async def main():
    """執行基準測試"""
    benchmark = PerformanceBenchmark()

    # 測試 1: 延遲比較
    print("🧪 測試 1: 延遲比較...")

    await benchmark.benchmark_latency(
        handler=mock_current_handler,
        test_name="latency_test",
        architecture="current",
        num_calls=100
    )

    await benchmark.benchmark_latency(
        handler=mock_optimized_handler,
        test_name="latency_test",
        architecture="optimized",
        num_calls=100
    )

    # 測試 2: 高負載測試
    print("\n🧪 測試 2: 高負載測試...")

    await benchmark.benchmark_latency(
        handler=mock_current_handler,
        test_name="load_test",
        architecture="current",
        num_calls=50
    )

    await benchmark.benchmark_latency(
        handler=mock_optimized_handler,
        test_name="load_test",
        architecture="optimized",
        num_calls=50
    )

    # 生成報告
    benchmark.generate_report()


if __name__ == "__main__":
    asyncio.run(main())
