# ADR-076: worker 返回 None 与抛异常同等不可见，并行路径必须一并留痕

## 状态

接受

## 日期

2026-10-04

## 影响组件

- `tools/scripts/rules_engine/performance.py`（`_parallel_check`）
- `tests/test_performance_worker_none_observable.py`（新增，3 个用例）

## 背景

`test_optimized_check_directory_parallel` 的偶发失败此前一直未定位，
ADR-074 只修掉了「worker 抛异常」这一条分支的静默丢结果。本轮不再重复
压力测试（四轮约 50 次尝试全阴性，边际收益已趋零），改为**穷举代码分支**
做静态分析，由此发现 ADR-074 **只修了一半**。

## 缺陷

`_parallel_check` 的失败处理长这样：

```python
try:
    result = future.result()
    results.append(result)  # ← result 为 None 也走这里, 无任何记录
except Exception as exc:
    self.failed_files[filepath] = ...
    results.append(None)
```

而 worker 函数 `_check_file_worker` 内部是这样的：

```python
try:
    result = check_file(...)
    return {...}
except (AttributeError, OSError):
    return None  # ← 失败被吞成 None
```

即：worker **抛异常** 会留痕，worker **返回 None**（更常见的失败形态）
**完全不留痕**。该文件随后被 `optimized_check_directory` 的
`[r for r in results if r is not None]` 静默剔除。

`failed_files` 里也确实记了 —— 但只在 `_serial_check` 里记。并行路径
没有。两条路径对同一故障的行为**不一致**。

## 为什么这正是那个偶发失败的形态

故障注入后实测（6 个文件，2 个返回 None）：

```
[并行] 结果数=4, failed_files=[]            ← 结果变少, 但毫无线索
[串行] 结果数=4, failed_files=['f2.py','f4.py']
```

而原用例的失败现象正是：**结果数少于文件数，`failed_files` 却查不到
任何东西**。ADR-074 之前，两者都是空；ADR-074 之后，抛异常有了记录，
但返回 None 这一支仍然静默 —— 恰好是这个用例最可能踩到的那一支。

这解释了为什么此前四轮排查都抓不到：现场无法构造出「worker 返回
None」，于是永远只能观察到「`failed_files` 为空」这一非特异性症状。

## 决策

并行路径在 `result is None` 时同样写入 `failed_files`，与串行路径对齐。

保留 `None` 占位不动 —— 上层 `optimized_check_directory` 的过滤行为、
既有返回契约、ADR-074 的用例均不受影响。改动只增加可观测性，不改变
「检查通过」的判定。

## 验证

### 变异验证

| 状态 | 结果 |
|------|------|
| 修复前 | 2 failed / 1 passed |
| 修复后（连跑 3 次） | 3 passed |
| 变异：去掉 `result is None` 留痕（连跑 3 次） | 2 failed / 1 passed，3 次均捕获 |

失败信息直指缺陷本身：
`worker 返回 None 的文件未记入 failed_files, 实得 []`。

健康对照 `test_healthy_control_no_spurious_failures` 在全部三种状态下
均通过，确认修复不会凭空产生 `failed_files`。

`tests/test_performance_extended.py`（含 ADR-074 用例）14 passed 未受影响。

### 测试设计上的一个陷阱（记录在此以免重犯）

第一版用**局部闭包**作为注入 worker，结果 `ProcessPoolExecutor` 在
pickle 阶段就抛 `AttributeError: Can't pickle local object`，所有 worker
走的是「抛异常」分支 —— 测到的成了 ADR-074 已修好的东西，**不是**本文
要指的「返回 None」分支。

第二版改用模块级函数，但又踩一个坑：注入函数内部调用
`FileCache._check_file_worker(args)` 取真实 worker，而 fork 出的子进程
继承的是**已打补丁**的属性，于是无限递归，表现为「结果数=0、
所有文件都失败」。

最终解法：模块级函数 + 在**导入时**用模块级常量 `_REAL_WORKER` 捕获真实
worker。教训：给 `ProcessPoolExecutor` 做故障注入时，注入函数与被测
真实函数之间的引用关系必须在 fork 之前就固定下来。

## 影响范围

`rules_engine/performance.py` 文档自述**无生产调用方**（仅
`perf_benchmark.py` 与测试引用），故本修复影响面限于基准与测试。

## 与未定位偶发失败的关系

**本 ADR 不声称解决了 `test_optimized_check_directory_parallel` 的偶发
失败。** 已确定的是：它修掉了一条真实的静默 fail-open 缺陷，且该缺陷的
外部表现与该用例的失败现象一致（结果变少 + `failed_files` 为空）。

但**触发条件仍未定位**：没有证据表明真实运行中 worker 会返回 None。
若再次发生，现在 `failed_files` 会直接给出文件名与原因，无需再靠猜测 ——
这正是本 ADR 的实际价值：把「不可观测」变成「可观测」。

诚实边界：这是一条**已复现并验证的缺陷修复**，不是对那个偶发失败的
根因确认。
