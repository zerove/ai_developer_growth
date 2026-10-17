---
title: ADR-078: worker 崩溃必须变成 error 级 Issue，不得静默剔除文件
description: ## 状态
category: 治理层
tags: ['Python', '测试', 'check', 'AI', 'ADR']
difficulty: 初级
reading_time: 10 分钟
updated: 2026-07-21
---

# ADR-078: worker 崩溃必须变成 error 级 Issue，不得静默剔除文件

## 状态

接受

## 日期

2026-10-05

## 影响组件

- `tools/scripts/adg_cli/check.py`（`_make_check_error_issue` 新增；`_run_checks` 串行分支、`_check_files_parallel` 加固）
- `tools/scripts/adg_cli/commands/cmd/cmd_check.py`（`_run_checks` 串行分支加固）
- `tools/scripts/adg_cli/commands/cmd/_shared.py`（再导出 `_make_check_error_issue`）
- `tests/test_check_error_propagation.py`（新增，12 个用例）

## 背景

这是 ADR-074（worker 失败必须可观测）与 ADR-076（worker 返回 `None`
必须留痕）的**第三处同类缺陷**，前两处已修，此处未修。

发现路径：按 CI 真实口径（`pytest --cov=tools --cov=.jcode/scripts`）跑全量时，
`tests/test_adg_cmd_integration.py::TestCmdCheckExtended::test_check_with_jobs_parallel`
偶发失败（5088 passed / 1 failed）。单独重跑通过、并行下连跑 10 次全绿，
**因此无法证明它由本次改动引起**。但在追查该 flake 的过程中读到了
`_check_files_parallel` 的实现，确认了一个**独立的、可确定性复现的**缺陷。

需要明确区分两件事：

- **已证实**：worker 崩溃会被静默剔除，导致 `adg check` fail-open（见下）。
- **未证实**：该缺陷就是上述 flake 的成因。flake 至今未能复现。

本 ADR 只处理前者。

## 缺陷

`_check_files_parallel` 对 worker 异常只打印警告：

```python
for future in as_completed(future_to_file):
    try:
        issues = future.result()
        all_issues.extend(issues)
    except Exception as e:
        # Log error but continue processing
        filepath = future_to_file[future]
        print(f"Warning: Error checking {filepath}: {e}", file=sys.stderr)
```

崩溃的文件**从结果里彻底消失**。调用方拿到的 issue 列表与
"该文件干净"**无法区分** —— 这是 ADR-074/076 已经明确禁止的形态，
此处却仍在使用。于是 `adg check` 对一个**实际根本没被检查**的文件
返回退出码 0（fail-open）。

串行分支则走向另一个极端：**完全不捕获**，worker 等价的异常会
让整个 `check` 崩溃，用户看到的是 traceback 而不是问题报告。

### 实测（修复前）

用 fork 继承 patch 模块级 `check_file`，使 `boom.py` 在 worker 内抛异常，
`clean.py` 正常返回一个 `error`：

```
并行(jobs=2) 返回 issue 数=1   并行退出码 = 1
串行(jobs=1) 返回 issue 数=0   串行直接抛出 RuntimeError
```

关键在于：**并行与串行对同一输入给出不同结果，且两者都不正确**。

- 并行：崩溃文件被静默剔除。该文件实际未被检查，却不体现在任何输出中。
- 串行：整体崩溃，一个文件的故障导致全量检查无结果。

注意并行那行的退出码 1 具有**欺骗性** —— 它来自 `clean.py` 自身的
`error`，与崩溃无关。若夹具中所有正常文件都不报 error，并行会返回
退出码 0，即静默放行。

## 决策

把"文件检查失败"本身**升格为一条 `check-error` 级别的 `error` Issue**，
而不是继续 `print`。

```python
def _make_check_error_issue(filepath: Path, exc: BaseException) -> Issue:
    return Issue(
        rule_id="check-error",
        severity="error",
        category="infrastructure",
        file=str(filepath),
        line=1,
        column=1,
        message=f"检查失败，该文件未被检查: {type(exc).__name__}: {exc}",
        fix_hint="检查该文件是否可读、是否被其他进程占用，或用 --jobs 1 重试",
    )
```

选择 `error` 而非 `warning` 是**刻意的**：CI 依据退出码判断成败，
只有 `error` 才能保证失败不会被放过。降级为 `warning` 会让修复形同虚设
（见下方变异 M2）。

并行与串行**两条路径都要走这个 helper**，从而保证对同一输入给出相同的
issue 集合与相同的退出码。串行路径同时从"整体抛出"改为"报告问题"。

保留原有的 `print` 到 stderr：它对交互式使用有价值，且不与结构化记录冲突
（ADR-074/076 的教训是"只 print 不留结构"，而非"不许 print"）。

## 后果

- `adg check --jobs N` 在有文件崩溃时退出码必然非零，不再 fail-open。
- 崩溃文件出现在 issue 输出中，`--json` 等格式也能带上。
- 串行路径不再因单文件故障整体崩溃。
- 行为变更：此前被静默跳过的崩溃场景现在会**让 CI 失败**。这是预期结果 ——
  它揭示的是真实的漏检，而不是制造新问题。

## 验证

`tests/test_check_error_propagation.py`，12 个用例。断言全部落在
**用户可见行为**上（退出码、issue 集合），沿用 ADR-077 的教训：
只盯被改动的那个字节会漏掉整类缺陷。

探针机制：Linux 默认 start method 为 `fork`，子进程继承父进程内存，
故在父进程 patch 模块级 `check_file` 对 worker 同样生效 —— 无需真正
制造 I/O 故障即可稳定触发 worker 内异常。

变异测试（全部被杀）：

| 变异 | 结果 |
|---|---|
| 健康基线 | 12 passed |
| M1 恢复并行吞异常（只 print 不留痕） | 5 failed / 7 passed |
| M2 `check-error` 降级为 `warning` | 2 failed / 10 passed |
| M3 串行路径去掉 `try`（恢复整体抛出） | 6 failed / 6 passed |

M2 最初只杀死 1 个测试。原因是 `test_same_exit_code` 的夹具里
`clean.py` 本身就返回 `error`，把降级后的失败信号淹没。补上
`test_crash_alone_forces_nonzero_exit`（**只有崩溃文件**、排除其他
error 来源）后杀死数升到 2。

这本身是一个可复用的教训：**当夹具中存在其他能独立触发同一信号的
因素时，等价性断言会失去辨别力**。断言必须隔离出被测因素。

## 关联

- ADR-074：worker 抛异常静默丢结果（本 ADR 是其未修尽的第三处）
- ADR-076：worker 返回 `None` 不留痕
- ADR-077：断言必须落在用户可见行为上（本 ADR 的测试设计依据）
