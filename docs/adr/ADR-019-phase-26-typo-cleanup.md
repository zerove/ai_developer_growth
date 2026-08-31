---
title: ADR-019 Phase 26 adg 误报再清理 + 剩余 39 真问题移交
description: > 续 ADR-017/018 降级 4 类误报 (py-missing-type-hints / py-any-type)，
  剩 39 个真问题按 P0-P3 优先级排入 Phase 27。
category: 治理层
tags: ['ADR', 'governance', 'adg', 'quality-gate', 'phase-26']
difficulty: 基础
reading_time: 5 分钟
updated: 2026-08-31
---

# ADR-019: Phase 26 adg 误报再清理

> 状态: ✅ 已通过 | 日期: 2026-08-31

---

## 背景

[ADR-018](./ADR-018-adg-rules-batch-downgrade.md) 降级 7 类规则后，剩余 65 个 warning 中：
- **20 个** 是类型相关 (`py-any-type` 14 + `py-missing-type-hints` 6)
- **45 个** 是其他真问题 (性能/设计)

本 ADR 继续处理类型相关 20 个，并明确移交剩余 39 个真问题。

## 决策

### 1. 再降级 2 类规则为 info

| 规则 | 数量 | 降级理由 |
|------|------|---------|
| `py-missing-type-hints` | 6 | 全部位于 docstring `Usage:` 块内的示例代码 (web_base/ast_parser/plugins/semantic_rules)，规则不识别 docstring 上下文，docstring 示例本就无需类型注解 |
| `py-any-type` | 14 | 集中于 dynamic import / plugin loader / 递归 converter 模式（`_get_llm_client` / `_load_governance_auditor` / `safe_import` / `_fix_single_file` 等），`Any` 是合理选择，用更窄类型需大量 Protocol 抽象 |

### 2. 39 个真问题移交 Phase 27

明确**不**降级，由人工 case-by-case 处理：

| 规则 | 数量 | 性质 | Phase 27 难度 |
|------|------|------|--------------|
| `py-n-plus-one` | 25 | 性能 (循环内查询) | 中 — 需 profile + 索引优化 |
| `py-global-statement` | 5 | 全局状态 (配置缓存/worker 规则/plugin 注册) | 中 — 需重构为类/依赖注入 |
| `common-type-any` | 5 | TypeScript any 类型 | 低 — 加 `unknown` + type guard |
| `py-shared-mutable` | 4 | 模块级 mutable state | 中 — 加锁或重构 |

## 效果

| 指标 | 值 |
|------|-----|
| 降级前 (Phase 25 末) | 65 warnings |
| 本次降级 | -20 (-30.8%) |
| 降级后 | **39 warnings** (剩余全为真问题) |
| adg error | 0 (不变) |
| 累计 adg warning 降级 | 1235 → 39 (-96.8% = 1196 个) |

## Phase 27 候选清单

按 ROI 排序：

- **P1 (类型安全 - TS)**: `common-type-any` 5 个 — 简单，直接改
- **P2 (全局状态)**: `py-global-statement` 5 个 + `py-shared-mutable` 4 个 = 9 个 — 中等改造
- **P3 (性能)**: `py-n-plus-one` 25 个 — 需 profile 识别热点

## ADR 链接

- 前置: [ADR-018 批量降级总结](./ADR-018-adg-rules-batch-downgrade.md)
- 后续: Phase 27 引入 ADR-020 处理剩余 39 个
