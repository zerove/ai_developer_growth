---
title: 架构决策记录 (ADR) 索引
description: > 本文件汇总所有架构决策记录，按时间倒序排列。
category: 治理层
tags: ['REST']
difficulty: 基础
reading_time: 10 分钟
updated: 2026-08-29
---

# 架构决策记录 (ADR) 索引

> 本文件汇总所有架构决策记录，按时间倒序排列。

---

## ADR 列表

| ID | 标题 | 状态 | 日期 |
|----|------|------|------|
| [[ADR-018-adg-rules-batch-downgrade\|ADR-018]] | adg 规则批量降级总结 (7 类 → info) | ✅ 已通过 | 2026-08-31 |
| [[ADR-017-py-log-print-downgrade\|ADR-017]] | py-log-print 误报降级为 info (CLI 入口面向用户输出) | ✅ 已通过 | 2026-08-31 |
| [[ADR-016-close-pending-adrs\|ADR-016]] | 关闭 4 个长期未决 ADR (005/007/008/011) | ✅ 已通过 | 2026-08 |
| [[ADR-015-pytest-xdist-race-condition\|ADR-015]] | pytest-xdist race condition 接受现状 | ✅ 已通过 | 2026-08 |
| [[ADR-013-pytest-xdist-coverage-known-issue\|ADR-013]] | 覆盖率报告"假 0%" 现象（误判根因已修订） | 🔄 修订 | 2026-08 |
| [[ADR-012-vector-rag-not-core\|ADR-012]] | 向量 RAG 不作为 ai_developer_growth 检索核心 | ✅ 已通过 | 2026-08 |
| [[ADR-011-phase18-ai-native-dialogue-community-cleanup\|ADR-011]] | Phase 18: P1 对话界面 + P2 社区案例清理 + AI-Native 生态完善 | 🚫 已拆分关闭 | 2026-08 |
| [[ADR-010-community-growth-infrastructure\|ADR-010]] | P2 社区增长基础设施：自动化验证、激励体系、Issue 标准化 | ✅ 已通过 | 2026-08 |
| [[009-ci-cd-optimization-security\|ADR-009]] | CI/CD 流水线优化与安全强化 | ✅ 已通过 | 2026-08 |
| [[008-production-grade-workflow\|ADR-008]] | 生产级稳健工作流与防御性接口设计 | ✅ 已通过 | 2026-08 |
| [[007-m4-ai-navigation-design\|ADR-007]] | M4 AI 导航系统设计 | 🚫 已废弃 | 2026-07 |
| [[005-ai-navigation-system\|ADR-005]] | AI 导航系统架构 | 🚫 已废弃 | 2026-07 |
| [[004-agent-collaboration-model\|ADR-004]] | 多 Agent 协作模型与编排模式 | ✅ 已通过 | 2026-07 |
| [[003-quality-gate-system\|ADR-003]] | 四道质量门禁系统设计 | ✅ 已通过 | 2026-07 |
| [[002-refactor-validate-language-rules\|ADR-002b]] | 重构 validate_language_rules.py 模块化 | ✅ 已通过 | 2026-07 |
| [[002-knowledge-first-restructure\|ADR-002]] | 知识优先重构——项目定位重定向 | ✅ 已通过 | 2026-07 |
| [[001-language-rules-engine-architecture\|ADR-001b]] | 语言规则引擎架构设计 | ✅ 已通过 | 2026-07 |
| [[001-enhanced-git-analyzer\|ADR-001]] | 增强 Git 变更解析的鲁棒性 | ✅ 已通过 | 2026-07 |

---

## ADR 模板

新建 ADR 请复制以下模板，保存为 `docs/adr/ADR-{ID}-{title}.md`：

```markdown
# ADR-{ID}: {标题}

## 状态
{草稿 | 已通过 | 已废弃 | 已取代}

## 上下文
{描述问题背景和约束条件}

## 决策
{描述选择的方案和理由}

## 影响
{描述决策带来的正面和负面影响}

## 相关 ADR
- {如有依赖或取代关系，列出相关 ADR}
```

---

## 编号规则

- 格式: `ADR-{三位数字}-{简短标题}`
- 递增编号: ADR-001, ADR-002, ...
- 标题使用 kebab-case: `ADR-002-add-caching-layer`

---

## 创建流程

1. 识别需要记录的架构决策
2. 复制上方模板
3. 填写四部分内容
4. 提交 PR，等待评审
5. 合并后更新本索引

---

*本索引随新增 ADR 时更新。最后更新: 2026-08-29*
