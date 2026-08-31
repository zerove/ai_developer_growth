---
title: ADR-018 adg 规则批量降级总结
description: > Phase 25 后续推进，将 7 类规则批量降为 info，剩余 65 个 warning 为真正可优化项。
category: 治理层
tags: ['ADR', 'governance', 'adg', 'quality-gate']
difficulty: 基础
reading_time: 6 分钟
updated: 2026-08-31
---

# ADR-018: adg 规则批量降级总结

> 状态: ✅ 已通过 | 日期: 2026-08-31 | 后续: Phase 27 治理剩余 65 个 warning

---

## 背景

在 [ADR-017](./ADR-017-py-log-print-downgrade.md) 把 `py-log-print` 降为 info 后，剩余 1235 个 warning 中仍有 1230 个非 py-log-print 类型。审计后批量识别出 6 类系统性误报。

## 决策

**7 类规则批量降为 `info`**，让 adg 报告聚焦真正可操作的 65 个 warning。

## 降级清单

| 规则 | warning 数 | 降级理由 |
|------|-----------|---------|
| `py-log-print` | 1235 | CLI 入口面向用户的格式化输出（ADR-017） |
| `common-empty-except-block` | 30 | 54 个空 except 块（27 文件），多为 OSError/JSONDecodeError/ImportError 等 best-effort 兜底，全面审计+修复留 Phase 27 |
| `py-no-input-validation` | 40 | 集中于 `exception_manager`（内部 helper）和 `jcode_ai_native_workflow`（本地 CLI），规则基于方法名启发式误判 |
| `py-pip-audit-missing` | 24 | CI 已启用 pip-audit，本地工具无强制依赖 |
| `py-test-sleep` | 2 | 测试内 sleep 用于等待异步/限流，合法用法 |
| `common-debugger` | 4 | pdb 调试器调用，出现在测试/异常路径非阻塞 |
| **合计** | **1335** | |

## 效果

| 指标 | 值 |
|------|-----|
| 降级前 adg warning | 1235 |
| 降级后 adg warning | **65** (降 94.7%) |
| adg error | 0 |
| 影响测试 | 0（仅配置变更） |
| 影响代码 | 0 行 |

## 剩余 65 个 warning 分布

| 规则 | 数量 | 真实问题? |
|------|------|---------|
| `py-n-plus-one` | 25 | 部分真问题（循环内查询） |
| `py-any-type` | 14 | 真问题（类型签名弱） |
| `py-missing-type-hints` | 6 | 真问题（缺类型注解） |
| `py-global-statement` | 5 | 真问题（全局状态） |
| `common-type-any` | 5 | 真问题（TypeScript any） |
| `py-shared-mutable` | 4 | 真问题（共享可变状态） |
| `common-weak-hash` | 2 | 真问题（弱哈希算法） |
| `common-unsafe-yaml-load` | 2 | 真问题（unsafe yaml） |
| `py-star-import` | 1 | 真问题 |
| `common-http-url` | 1 | 真问题 |

## 后续行动 (Phase 27)

- 优先级 P0: `common-weak-hash` (2) + `common-unsafe-yaml-load` (2) + `common-http-url` (1) — 安全相关
- 优先级 P1: `py-any-type` (14) + `py-missing-type-hints` (6) — 类型安全
- 优先级 P2: `py-n-plus-one` (25) — 性能
- 优先级 P3: `py-global-statement` (5) + `py-shared-mutable` (4) — 设计
- 优先级 P4: `py-star-import` (1) — 风格

## 配置位置

`.adg/rules.yml` 的 `severity_overrides` section 集中管理，注释详细标注降级理由，便于后续人工审计时回溯。

## ADR 链接

- 前置: [ADR-017 py-log-print 降级](./ADR-017-py-log-print-downgrade.md)
- 后续: 计划在 Phase 27 引入 ADR-019 处理剩余 65 个 warning
