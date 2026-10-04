# ADR-074: worker 失败不得静默丢结果，必须留下可追溯痕迹

## 状态

接受

## 日期

2026-10-03

## 影响组件

- `tools/scripts/rules_engine/performance.py`（`PerformanceOptimizer.failed_files`、`_parallel_check`、`_serial_check`、`optimized_check_directory`）
- `tests/test_performance_extended.py`（`TestWorkerFailureIsNotSilent`）

## 背景

ADR-073 收口时在全量 `-n 8` 下观测到一次
`test_optimized_check_directory_parallel` 偶发失败（约 9 次全量里
1 次，单独跑恒绿）。追查时先给出一个**错误**的归因，此处一并记录，
因为错误的归因比缺陷本身更容易误导后续修复。

### 错误归因及其证伪

最初判断是 `future.result(timeout=30)` 在高负载下超时，worker 被
记为 `None` 并从结果中剔除。

**该判断错误。** `as_completed()` 只产出**已完成**的 future，因此
对其调用 `result(timeout=...)` 不可能超时 —— 那行 timeout 是死代码。
证伪方式：用 `result(timeout=0.001)` 对 `as_completed()` 产出的
future 取值，全部正常返回，不抛 `TimeoutError`。

真实触发条件是 **worker 抛异常**，与超时无关。

### 真实缺陷

`_parallel_check` 原先写成：

```python
except (TimeoutError, Exception):
    results.append(None)
```

随后 `optimized_check_directory` 用

```python
all_results = cached_results + [r for r in results if r is not None]
```

把所有 `None` 剔除。两者叠加的效果是：**worker 崩溃的文件从返回值
里彻底消失，不报错、不计数、不留任何痕迹。**

确定性复现：注入 3 个抛异常的 worker，提交 10 个文件，
`optimized_check_directory` 只返回 7 条，全程零诊断输出。

调用方无法区分「检查通过且没问题」与「根本没检查到」，这与本项目
「门禁不可 fail-open」的既定约束（见 `CONTEXT.md` 关键约束）直接冲突。

串行路径 `_serial_check` 有**同一个洞**：`_check_file_worker` 内部
`except (AttributeError, OSError): return None`，返回值同样被静默剔除。

## 决策

### 1. 保留既有返回契约，但让失败可观测

**不改** `None` 占位与 `if r is not None` 的过滤行为 —— 那是既有
契约，`perf_benchmark.py` 等调用方依赖它，贸然改成抛异常会把一个
静默缺陷换成一个 CI 崩溃。

改为新增 `self.failed_files: dict[str, str]`（filepath → 原因）：

- 每次 `optimized_check_directory` 开头清空，避免上一轮污染本轮；
- 并行路径记录异常类型与消息；
- 串行路径记录 `worker returned None` 这一事实。

调用方现在可以区分「检查通过」与「没检查到」，fail-open 被消除，
且不破坏任何现有调用方。

### 2. 顺带移除死代码

`future.result(timeout=30)` 改为 `future.result()`。既然 `as_completed`
已保证完成，保留一个永不生效的超时只会误导下一个读者 —— 这正是本次
误判的来源。留着它等于把同一个陷阱再埋一次。

### 3. 测试不得依赖跨进程 monkeypatch

本次踩到两个**测试侧**陷阱，都不体现在产品代码里，但会让回归测试
变成假绿灯：

- **局部闭包不可 pickle。** `ProcessPoolExecutor` 要 pickle callable，
  注入的 worker 必须是模块级函数，否则全部 worker 失败（表现为
  `results` 为空，而非预期）。
- **pytest 下 start method 是 `forkserver`。** 由 hypothesis 插件
  设置（干净解释器里是 `fork`）。forkserver 会**重新导入 `__main__`**，
  父进程的 `monkeypatch` 对子进程不可见 —— 跨进程注入 worker 在
  pytest 里**根本不可能生效**。

因此测试改用 `_FakeFuture` + `_StubExecutor` 直接驱动
`_parallel_check`，精确覆盖「future 抛异常」这条分支，且不依赖
平台、不依赖 start method、不依赖子进程调度。

## 后果

### 正面

- worker 失败从「静默消失」变为「`failed_files` 中可查」；
- 移除一个会持续误导读者的死代码 timeout；
- 新增 5 条回归测试，其中 1 条为**健康代码对照**
  （`test_healthy_parallel_run_leaves_failed_files_empty`），
  防止「无条件记录失败」这类假修复蒙过测试。

### 影响面有限（据实说明）

本模块文档头部自述**无生产调用方**，仅 `perf_benchmark.py`
（基准工具）与测试引用。故本次修复当前不改变任何生产行为，
属于消除 fail-open 隐患而非修复线上故障。

`test_optimized_check_directory_parallel` 的偶发失败**触发条件尚未
定位**：修复后连续 7 次全量 `-n 8` 均通过，未再复现。不能断言
本次修改解决了它 —— 已修复的是**已确定性复现的静默丢结果缺陷**，
偶发失败可能另有原因。

## 验证方式

每处变异单独确认，且确认对照组保持绿：

| 变异 | 结果 |
|------|------|
| 仅回退并行路径的失败记录 | 3 failed（并行记录 + 重置 + 端到端可观测） |
| 仅回退串行路径的失败记录 | 1 failed（串行记录），并行相关用例保持绿 |

还原后 `tests/test_performance_extended.py` 14 passed。
