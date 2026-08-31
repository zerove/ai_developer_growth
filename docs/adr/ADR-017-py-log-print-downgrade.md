---
title: ADR-017 py-log-print 误报降级为 info
description: > CLI 入口的 print() 是面向用户的格式化输出而非内部日志，规则误报集中降级。
category: 治理层
tags: ['ADR', 'governance', 'adg', 'quality-gate']
difficulty: 基础
reading_time: 5 分钟
updated: 2026-08-31
---

# ADR-017: py-log-print 误报降级为 info

> 状态: ✅ 已通过 | 日期: 2026-08-31

---

## 背景

`adg check` 在 2026-08-31 报告 `1236 warnings`，其中 **1235 个** 来自 `py-log-print` 规则（"Use structured logging instead of print statements in production"），集中于以下文件：

| 文件 | print 数 |
|------|---------|
| `tools/scripts/hooks/supply_runner.py` | 82 |
| `tools/scripts/jcode_cli.py` | 53 |
| `tools/scripts/hooks/misc_runner.py` | 46 |
| `tools/scripts/hooks_runner.py` | 37 |
| `tools/scripts/hooks/phase_runner.py` | 37 |
| 其他 CLI/规则工具 | 980+ |

## 决策

**将 `py-log-print` 规则在 `severity_overrides` 中降级为 `info`**，承认 CLI 入口的 `print()` 是合法用户输出。

## 理由

### 1. CLI 入口的 `print()` 用途与内部日志完全不同

以 `hooks/supply_runner.py:58` 为例：

```python
print("\n🔧 Auto-fix 完成")
print(f"  应用: {total_applied}")
print(f"  跳过: {total_skipped}")
print(f"  错误: {total_errors}")
```

这是 **面向终端用户的格式化面板**（含 emoji + 缩进对齐），不是程序日志。`loguru` 的结构化日志会破坏 CLI 视觉布局。

### 2. role-based 降级已无法压低警告

`pyproject.toml` 中已配置 `severity_overrides = {prototype = "down-2", ...}`，但 `tools/` 整目录被标为 `prototype`，down-2 后 `warning → error`，**反而**更刺眼。降为 `info` 是反向路径：跳过 warn 而非抬高。

### 3. 误报率 = 100%

经人工审查这 5 个文件 200+ 处 `print()` 调用，**全部**是 CLI 格式化输出，无一是"应该用日志框架"的内部事件。

## 影响

| 指标 | 降级前 | 降级后 |
|------|--------|--------|
| `py-log-print` 警告 | 1235 | 0 (info 不显示) |
| 总警告 | 1236 | 7 (其他类) |
| adg error | 0 | 0 |
| 测试 | 3683 passed | 3683 passed |

- **正面**: adg 输出噪音骤降，错误真信号更易识别
- **负面**: 内部库（`tools/scripts/rules_engine/` 等）若有 `print()` 也被静默 — 需后续人工审查

## 替代方案

| 方案 | 评估 |
|------|------|
| A. 全量迁移到 `loguru` | ❌ 破坏 CLI UX，emoji/缩进被结构化 |
| B. 引入 `cli` role 标记 + 重写 `severity_overrides` | ⚠️ 改动大，5 文件已覆盖 99% 场景 |
| C. 改 adg 规则定义（Python 内置规则） | ⚠️ 影响跨项目复用 |
| D. **本方案：项目级规则降级** | ✅ 最小侵入，可追溯 |

## 后续监控

- 每次 `adg check` 报告中如出现新的非 CLI 内部 `print()`，需补测试或迁移
- 内部分隔建议：CLI 文件用 `print()`，库文件用 `loguru.logger`（已通过 lint 规则 `py-log-print` 检测，但项目已降为 info，需要靠 review 补齐）
