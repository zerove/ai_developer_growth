---
title: ADR-020 Phase 26 收口与 Phase 27 移交
description: > adg warning 从 1235 降至 25 (-98%)，剩余 25 个 py-n-plus-one 留作 Phase 27 profile 验证。
category: 治理层
tags: ['ADR', 'governance', 'adg', 'phase-26', 'phase-27']
difficulty: 基础
reading_time: 6 分钟
updated: 2026-08-31
---

# ADR-020: Phase 26 收口与 Phase 27 移交

> 状态: ✅ 已通过 | 日期: 2026-08-31

---

## 背景

继 [ADR-019](./ADR-019-phase-26-typo-cleanup.md) 降级 2 类规则后，再处理 3 类共 14 个误报，并明确**不**对 25 个 `py-n-plus-one` 批量降级（保留作 Phase 27 真实工作清单）。

## 本次决策

### 1. 再降级 3 类规则

| 规则 | 数量 | 降级理由 |
|------|------|---------|
| `common-type-any` | 5 | 与 py-any-type 同类 (Python typing.Any 而非 TS any)，集中于 report_generator 的 `_build_*_testcase` helpers；引入 Protocol 抽象 ROI 低 |
| `py-global-statement` | 5 | 单进程 CLI 工具的缓存/注册表 (config 2 + worker init 1 + registry 1 + phase 1)；load-once/use-many，竞态风险低；重构 bug 风险 > 保留 global 风险 |
| `py-shared-mutable` | 4 | 与 py-global-statement 场景重叠；改造需类化/依赖注入 |
| **合计** | **14** | |

### 2. 暂不降级 1 类规则

`py-n-plus-one` 25 个保留不降级：

- 多数为**误报**（`for k, v in dict.items() 循环内 ToolCategory(k)` 枚举转换被启发式误判）
- 但仍**有少量真问题**风险（SQLite 循环查询、linter 多次子进程调用等）
- 防止规则"刷光" — 留 25 个**真实工作项**给 Phase 27
- Phase 27 用 profile 工具链（cProfile + line_profiler）逐个验证

## 最终治理指标

| 指标 | Phase 25 末 (v2.22.0) | Phase 26 收口 | 变化 |
|------|---------------------|---------------|------|
| adg error | 0 | 0 | — |
| adg warning | 1235 | **25** | **-98.0%** |
| adg info | 0 | 5520+ | 噪音转入 |
| 已降级规则类别 | 0 | **11 类** | — |
| ADR 数量 (Phase 25-26) | — | 4 (017-020) | — |
| 测试通过 | 3683 | 3683 | 保持 |
| Ruff | clean | clean | 保持 |
| 覆盖率 | 85.89% | 85.89% | 保持 |

## Phase 27 完整工作清单

### P0: 性能验证 (25 个)
- 25 个 `py-n-plus-one` warning 逐个 profile 验证
  - 用 `cProfile` + `line_profiler` 识别真实 N+1
  - 误报加 baseline 豁免，真问题做 batch/eager-load 优化

### P1: 文档同步
- 更新 ROADMAP Phase 27 段
- 新增 ADR-021 记录 Phase 27 profile 结果
- 更新 CHANGELOG v2.23.0 (Phase 27 收口后)

### P2: 工具增强（可选）
- 给 adg 加 `--baseline-from` 参数，支持项目级 baseline
- 给 adg 加 `py-n-plus-one` 的"启发式白名单"配置项（已知配置解析场景）

## 累计 ADR 索引 (Phase 25-26)

| ADR | 主题 |
|-----|------|
| [ADR-017](./ADR-017-py-log-print-downgrade.md) | py-log-print 误报降级 |
| [ADR-018](./ADR-018-adg-rules-batch-downgrade.md) | 7 类规则批量降级总结 |
| [ADR-019](./ADR-019-phase-26-typo-cleanup.md) | Phase 26: 2 类再降级 + 39 真问题移交 |
| [ADR-020](./ADR-020-phase-26-close-and-phase-27-handoff.md) | 本 ADR — Phase 26 收口 + Phase 27 移交 |

## 经验沉淀

- **规则降级是双刃剑**：批量降级可让报告聚焦，但过度降级会让项目"刷分"显得不真实
- **保留真问题作为工作清单**：拒绝批量降级 `py-n-plus-one` 是有意识的"信号保留"决策
- **每个降级都配 ADR**：从 0 类降到 11 类的全过程有 4 个 ADR 串联，未来审计可完整回溯
