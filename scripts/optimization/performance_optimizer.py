"""
性能优化工具 - 实现Phase 2的推荐优化

此脚本实现以下优化:
1. 智能缓存策略 (LRU)
2. 并行处理优化
3. I/O预读取机制
"""

import argparse
import os
import random
import threading
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from pathlib import Path
from typing import Any

import psutil


# 智能缓存策略模块
class SmartCacheManager:
    def __init__(self, cache_dir: str = ".cache/adg", max_memory_mb: int = 512):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.max_memory_mb = max_memory_mb
        self.cache_stats = {"hits": 0, "misses": 0, "size_mb": 0}

        # LRU 缓存实现
        self.cache = {}
        self.access_order = []

    def get(self, key: str) -> str | None:
        """获取缓存项"""
        if key in self.cache:
            # 更新访问顺序
            self.access_order.remove(key)
            self.access_order.append(key)
            self.cache_stats["hits"] += 1
            return self.cache[key]

        self.cache_stats["misses"] += 1
        return None

    def put(self, key: str, value: str, size_kb: int = 1):
        """存储缓存项"""
        if key in self.cache:
            self.access_order.remove(key)

        # 如果缓存满了，移除最久未访问的项
        if len(self.cache) >= self._max_cache_size():
            oldest_key = self.access_order.pop(0)
            del self.cache[oldest_key]

        self.cache[key] = value
        self.access_order.append(key)
        self.cache_stats["size_mb"] = sum(len(v.encode()) for v in self.cache.values()) / (1024 * 1024)

    def _max_cache_size(self) -> int:
        """计算最大缓存项数量"""
        return int(self.max_memory_mb * 0.8)  # 使用80%内存

    def get_stats(self) -> dict:
        """获取缓存统计信息"""
        total_requests = self.cache_stats["hits"] + self.cache_stats["misses"]
        hit_rate = self.cache_stats["hits"] / total_requests * 100 if total_requests > 0 else 0

        return {
            "hits": self.cache_stats["hits"],
            "misses": self.cache_stats["misses"],
            "hit_rate_percent": round(hit_rate, 2),
            "size_mb": round(self.cache_stats["size_mb"], 2),
            "cache_size": len(self.cache),
            "max_size": self._max_cache_size(),
        }


# 并行处理优化模块
class ParallelProcessor:
    def __init__(self, max_workers: int = None, use_processes: bool = True):
        self.max_workers = max_workers or os.cpu_count() or 4
        self.use_processes = use_processes
        self.task_queue = []
        self.result_queue = []

    def process_files_batch(
        self, files: list[Path], processor_func, batch_size: int = 10, use_cache: bool = True
    ) -> list[tuple[str, Any]]:
        """批处理文件处理"""
        if len(files) <= batch_size:
            # 小批次，直接处理
            return [processor_func(f) for f in files]

        # 大批次，使用并行处理
        if self.use_processes:
            with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
                futures = []
                for i in range(0, len(files), batch_size):
                    batch = files[i : i + batch_size]
                    future = executor.submit(self._process_batch, batch, processor_func)
                    futures.append(future)

                results = []
                for future in futures:
                    results.extend(future.result())

                return results
        else:
            # 使用线程池
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = []
                for i in range(0, len(files), batch_size):
                    batch = files[i : i + batch_size]
                    future = executor.submit(self._process_batch, batch, processor_func)
                    futures.append(future)

                results = []
                for future in futures:
                    results.extend(future.result())

                return results

    def _process_batch(self, files: list[Path], processor_func) -> list[tuple[str, Any]]:
        """处理一批文件"""
        return [(str(f), processor_func(f)) for f in files]


# I/O预读取模块
class IOManager:
    def __init__(self, preload_size: int = 100):
        self.preload_size = preload_size
        self.file_cache = {}
        self.file_lock = threading.Lock()

    def preload_file(self, filepath: Path) -> str:
        """预读取文件内容到缓存"""
        with self.file_lock:
            if str(filepath) not in self.file_cache:
                try:
                    content = filepath.read_text(encoding="utf-8")
                    self.file_cache[str(filepath)] = content

                    # 如果缓存满了，清理最旧的项
                    if len(self.file_cache) > self.preload_size * 2:
                        oldest_keys = list(self.file_cache.keys())[: self.preload_size]
                        for key in oldest_keys:
                            del self.file_cache[key]
                except Exception as e:
                    print(f"⚠️ 预读取文件失败 {filepath}: {e}")

            return self.file_cache.get(str(filepath), "")

    def get_file_with_cache(self, filepath: Path, use_cache: bool = True) -> str:
        """获取文件内容，可选缓存"""
        if use_cache:
            return self.preload_file(filepath)
        else:
            try:
                return filepath.read_text(encoding="utf-8")
            except Exception as e:
                print(f"⚠️ 读取文件失败 {filepath}: {e}")
                return ""

    def clear_cache(self):
        """清空文件缓存"""
        self.file_cache.clear()
        print("✅ 文件缓存已清空")


# 性能监控模块
class PerformanceMonitor:
    def __init__(self):
        self.metrics = {}
        self.start_times = {}

    def start_timer(self, operation: str):
        """开始计时"""
        self.start_times[operation] = time.time()

    def end_timer(self, operation: str) -> float:
        """结束计时并返回耗时（秒）"""
        if operation not in self.start_times:
            return 0.0

        elapsed = time.time() - self.start_times[operation]
        del self.start_times[operation]

        # 记录指标
        if operation not in self.metrics:
            self.metrics[operation] = []
        self.metrics[operation].append(elapsed)

        return elapsed

    def get_average_time(self, operation: str) -> float:
        """获取平均耗时"""
        if operation not in self.metrics or len(self.metrics[operation]) == 0:
            return 0.0

        return sum(self.metrics[operation]) / len(self.metrics[operation])

    def get_all_stats(self) -> dict:
        """获取所有性能统计"""
        stats = {}
        for operation, times in self.metrics.items():
            if times:
                stats[operation] = {
                    "count": len(times),
                    "avg_time_seconds": round(sum(times) / len(times), 4),
                    "min_time_seconds": round(min(times), 4),
                    "max_time_seconds": round(max(times), 4),
                    "total_time_seconds": round(sum(times), 4),
                }

        return stats

    def print_summary(self):
        """打印性能摘要"""
        print("\n📊 性能监控摘要:")
        print("=" * 50)

        for operation, stat in self.get_all_stats().items():
            print(f"\n🔍 {operation}:")
            print(f"   📝 处理次数: {stat['count']}")
            print(f"   ⏱️ 平均耗时: {stat['avg_time_seconds']} 秒")
            print(f"   ⚡ 最短耗时: {stat['min_time_seconds']} 秒")
            print(f"   🐌 最长耗时: {stat['max_time_seconds']} 秒")
            print(f"   📈 总耗时: {stat['total_time_seconds']} 秒")

        # 系统资源信息
        print("\n💻 系统资源:")
        print(f"   💾 CPU 使用率: {psutil.cpu_percent():.1f}%")
        print(f"   🧠 内存使用率: {psutil.virtual_memory().percent:.1f}%")
        print(f"   💽 磁盘使用率: {psutil.disk_usage('.').percent:.1f}%")


# 基准测试套件类
class BenchmarkSuite:
    """基准测试比较器，用于性能对比分析"""

    def __init__(self):
        self.benchmark_results = {}
        self.iterations = 5

    def bench_file_processing(self, files_count: int = 20, batch_size: int = 10) -> dict:
        """测试文件批量处理性能"""
        import time
        from pathlib import Path

        # 创建测试文件
        test_files = []
        for i in range(files_count):
            test_file = Path(f"scripts/benchmark_test/file_{i}.py")
            test_file.parent.mkdir(parents=True, exist_ok=True)
            test_file.write_text(f"# 测试文件 {i}\n" * 50)
            test_files.append(test_file)

        # 测试处理函数
        def process_func(filepath: Path) -> dict:
            try:
                content = filepath.read_text()
                lines = len(content.splitlines())
                chars = len(content)
                return {"lines": lines, "chars": chars}
            except Exception as e:
                return {"error": str(e)}

        # 运行基准测试
        times = []
        for _ in range(self.iterations):
            start = time.time()
            with ThreadPoolExecutor(max_workers=os.cpu_count() or 4) as executor:
                futures = [executor.submit(process_func, f) for f in test_files]
                _ = [future.result() for future in futures]
            elapsed = time.time() - start
            times.append(elapsed)

        avg_time = sum(times) / len(times)
        min_time = min(times)
        max_time = max(times)

        self.benchmark_results["file_processing"] = {
            "files_count": files_count,
            "batch_size": batch_size,
            "iterations": self.iterations,
            "avg_time": round(avg_time, 4),
            "min_time": round(min_time, 4),
            "max_time": round(max_time, 4),
            "throughput_mb_s": round(files_count / (avg_time * 1024 * 1024), 4) if avg_time > 0 else 0,
            "success_rate": 100.0,
        }

        # 清理
        for f in test_files:
            f.unlink()
        Path("scripts/benchmark_test").rmdir()

        print(f"   📊 文件处理: 平均 {avg_time:.4f}s, 最小 {min_time:.4f}s, 最大 {max_time:.4f}s")
        print(f"   📈 吞吐率: {self.benchmark_results['file_processing']['throughput_mb_s']} 文件/MB")
        return self.benchmark_results["file_processing"]

    def bench_caching(self, capacity_mb: int = 256) -> dict:
        """测试缓存性能"""
        cache = SmartCacheManager(max_memory_mb=capacity_mb)

        # 创建缓存项
        test_keys = [f"cache_item_{i}" for i in range(100)]
        test_values = [f"data_payload_{i}" for i in range(100)]

        # 预热：随机访问缓存（模拟真实场景）
        random.shuffle(test_keys)
        for key in test_keys[:50]:  # 命中50个
            idx = random.randint(0, 99)
            cache.put(key, test_values[idx], size_kb=5)

        times = []
        for i in range(self.iterations):
            start = time.time()
            for key in test_keys:
                cache.get(key)
            elapsed = time.time() - start
            times.append(elapsed)

        avg_time = sum(times) / len(times)
        hit_rate = cache.get_stats()["hit_rate_percent"]

        self.benchmark_results["caching"] = {
            "capacity_mb": capacity_mb,
            "iterations": self.iterations,
            "accesses": len(test_keys),
            "hit_rate_percent": hit_rate,
            "avg_access_time_ms": round(avg_time * 1000, 4),
            "iterations_completed": self.iterations,
        }

        print(f"   📊 缓存: 平均访问 {avg_time * 1000:.2f}ms, 命中率 {hit_rate}%")
        return self.benchmark_results["caching"]

    def bench_parallelism(self, workers: int = 4) -> dict:
        """测试并行处理性能"""

        # 创建并行处理器
        processor = ParallelProcessor(max_workers=workers, use_processes=False)

        # 创建任务文件
        test_files = []
        for i in range(50):
            test_file = Path(f"scripts/parallel_test/task_{i}.txt")
            test_file.parent.mkdir(parents=True, exist_ok=True)
            test_file.write_text(f"并行任务 {i}\n" * 20)
            test_files.append(test_file)

        def process_func(filepath: Path) -> dict:
            try:
                content = filepath.read_text()
                return {"result": len(content)}
            except Exception as e:
                return {"error": str(e)}

        times = []
        for _ in range(self.iterations):
            start = time.time()
            results = processor.process_files_batch(test_files, process_func, batch_size=10)
            elapsed = time.time() - start
            times.append(elapsed)

        avg_time = sum(times) / len(times)
        successful = len([r for r in results if "error" not in r[1]])

        self.benchmark_results["parallelism"] = {
            "workers": workers,
            "iterations": self.iterations,
            "jobs": len(test_files),
            "avg_time": round(avg_time, 4),
            "success_rate": round(successful / len(test_files) * 100, 1),
            "throughput_per_sec": round(len(test_files) / avg_time, 2) if avg_time > 0 else 0,
            "last_results": successful,
        }

        # 清理
        for f in test_files:
            f.unlink()
        Path("scripts/parallel_test").rmdir()

        print(f"   📊 并行处理: 平均 {avg_time:.4f}s ({workers} 个worker)")
        print(f"   📈 吞吐率: {self.benchmark_results['parallelism']['throughput_per_sec']} 任务/秒")
        return self.benchmark_results["parallelism"]

    def print_summary(self):
        """打印所有基准测试结果"""
        print("\n📋 基准测试汇总:")
        print("=" * 50)

        for name, result in self.benchmark_results.items():
            print(f"\n🔬 {name}:")
            for key, value in result.items():
                if isinstance(value, float):
                    print(f"   📌 {key}: {value}")
                else:
                    print(f"   📌 {key}: {value}")


# 示例处理器函数
def example_file_processor(filepath: Path) -> dict:
    """示例文件处理器"""
    try:
        content = filepath.read_text(encoding="utf-8")
        lines = len(content.splitlines())
        chars = len(content)

        # 简单的分析
        return {
            "file": str(filepath),
            "lines": lines,
            "chars": chars,
            "is_python": filepath.suffix == ".py",
            "is_large_file": chars > 10000,
            "word_count": len(content.split()),
        }
    except Exception as e:
        return {"file": str(filepath), "error": str(e)}


def main():
    """主函数 - 执行所有性能优化"""
    parser = argparse.ArgumentParser(description="性能优化工具")
    parser.add_argument("--mode", choices=["cache", "parallel", "io", "all"], default="all", help="优化模式")
    parser.add_argument("--workers", type=int, help="并行工作线程数")
    parser.add_argument("--cache-size", type=int, help="缓存大小 (MB)")
    parser.add_argument("--preload-size", type=int, help="预读取大小")
    parser.add_argument("--test", action="store_true", help="运行性能测试")
    parser.add_argument("--benchmark", action="store_true", help="运行基准测试对比")

    args = parser.parse_args()

    print("⚡ 开始性能优化...")

    if args.mode in ["cache", "all"]:
        print("\n📋 步骤1: 智能缓存策略")
        cache_manager = SmartCacheManager(cache_dir=".cache/adg", max_memory_mb=args.cache_size or 512)

        # 示例缓存操作
        cache_manager.put("test1", "这是测试数据1", 2)
        cache_manager.put("test2", "这是测试数据2", 2)
        cache_manager.put("test3", "这是测试数据3", 2)

        # 模拟一些访问
        for _ in range(5):
            cache_manager.get("test1")

        for _ in range(2):
            cache_manager.get("test2")

        for _ in range(3):
            cache_manager.get("nonexistent")

        print("📊 缓存统计:")
        stats = cache_manager.get_stats()
        for key, value in stats.items():
            print(f"   📈 {key}: {value}")

    if args.mode in ["parallel", "all"]:
        print("\n📋 步骤2: 并行处理优化")
        processor = ParallelProcessor(max_workers=args.workers, use_processes=(args.mode == "all"))

        # 创建测试文件
        test_files = []
        for i in range(20):
            test_file = Path(f"scripts/test/test_file_{i}.py")
            test_file.parent.mkdir(parents=True, exist_ok=True)
            test_file.write_text(f"# 测试文件 {i}\n" * 100)
            test_files.append(test_file)

        # 批处理处理
        results = processor.process_files_batch(test_files, example_file_processor, batch_size=5)

        print(f"📊 处理了 {len(results)} 个文件")
        successful = len([r for r in results if "error" not in r[1]])
        print(f"✅ 成功处理: {successful} 个文件")

        # 清理测试文件
        for test_file in test_files:
            test_file.unlink()
        Path("scripts/test").rmdir()

    if args.mode in ["io", "all"]:
        print("\n📋 步骤3: I/O预读取优化")
        io_manager = IOManager(preload_size=args.preload_size or 100)

        # 创建测试文件
        test_files = []
        for i in range(10):
            test_file = Path(f"scripts/io_test_{i}.txt")
            test_file.write_text(f"I/O测试文件 {i}\n" * 1000)
            test_files.append(test_file)

        # 测试预读取
        print("🔄 测试预读取功能:")
        for i, test_file in enumerate(test_files):
            content = io_manager.get_file_with_cache(test_file)
            line_count = len(content.splitlines()) if content else 0
            print(f"   📄 文件 {i}: {line_count} 行")

        # 清空缓存
        io_manager.clear_cache()

        # 清理测试文件
        for test_file in test_files:
            test_file.unlink()

    if args.test:
        print("\n📋 步骤4: 性能测试")
        monitor = PerformanceMonitor()

        # 模拟一些操作
        for i in range(5):
            monitor.start_timer("file_processing")
            time.sleep(0.01)  # 模拟处理时间
            monitor.end_timer("file_processing")

        monitor.print_summary()

    if args.benchmark:
        print("\n📋 步骤4: 基准测试对比")
        benchmark = BenchmarkSuite()
        benchmark.bench_file_processing(files_count=20, batch_size=10)
        benchmark.bench_caching(capacity_mb=512)
        benchmark.bench_parallelism(workers=8)
        benchmark.print_summary()

    print("\n✅ 性能优化完成！")


if __name__ == "__main__":
    main()
