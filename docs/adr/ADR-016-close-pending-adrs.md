---
title: "ADR-016: 关闭 4 个长期未决 ADR (005/007/008/011)"
description: v2.16.0 治理收尾 — 重新评估 2026-07/08 提出的 4 个 ADR，确认现状与决策
category: 治理层
tags: ['ADR', 'governance', 'cleanup', '016']
difficulty: 中等
reading_time: 10 分钟
updated: 2026-08-29
---

# ADR-016: 关闭 4 个长期未决 ADR (005/007/008/011)

## 状态

**已通过** (2026-08-29)

## 上下文

5 个月+ 累积的 4 个长期未决 ADR 已影响 ADR.md 索引可读性，新增 ADR 易被陈旧 ADR 掩盖。本次集中评审：

| ADR | 提出日期 | 状态 | 关闭决策 |
|---|---|---|---|
| 005-ai-navigation-system | 2026-07-21 | ⏳ 提议 | ✅ **降级为已废弃** |
| 007-m4-ai-navigation-design | 2026-07-21 | 🔍 待评审 | ✅ **降级为已废弃** |
| 008-production-grade-workflow | 2026-08-25 | ⏳ 提议 | ✅ **通过** |
| 011-phase18-ai-native-dialogue-community-cleanup | 2026-08-19 | 🔍 提议中 | ✅ **拆分关闭** |

## 决策

### ADR-005 / ADR-007 关闭理由：降级为已废弃

两份 ADR 都描述"AI 导航系统"——基于向量/embedding 的对话式导师与个性化推荐。

**v2.16.0 P1-B 已用更轻量方案替代**：
- `tools/scripts/link_efficiency_cases.py` 实现双向链接自动化
- 76 个 ai-*.md 文档 100% 互链 case-studies
- 48 个 case-studies 89.6% 反向引用 ai-*.md
- 关键词匹配 + alias 映射覆盖 12 个语义域（架构/数据/API/前端/移动/devops/ML/Agent/爬虫/服务/治理/测试）

**未实施向量 RAG 原因**（同 ADR-012 已确立）：
- 知识库规模 < 500 文档，关键词检索足够
- 静态知识库约束 (无需数据库) 与向量索引冲突
- embedding 模型依赖增加维护成本

### ADR-008 关闭理由：通过

ADR-008 提出 4 项生产化改进，已在 v2.11+ 全部实施：

| 决策项 | 实施状态 | 证据 |
|---|---|---|
| 数据/逻辑解耦 | ✅ | `tools/scripts/rules_engine/ast_nodes.py` 仅 dataclass，无业务逻辑 |
| 防御性接口契约 | ✅ | Protocol 替代 ABC (v2.11) |
| 幂等修复策略 | ✅ | `fix.py:_apply_fix` 检查 has_match 后再写入 |
| loguru 结构化日志 | ✅ | `tools/scripts/jcode_ai_native_workflow.py` 全 loguru |

### ADR-011 关闭理由：拆分关闭

ADR-011 提出 3 大轨道（A 对话界面 / B 社区运营 / C 工具独立化），共 11+ 子任务。本次评估实际进展：

| 轨道 | 完成度 | 状态 |
|---|---|---|
| A. 对话界面与个性化导师 | 0% | 🚫 **废弃** (与 ADR-005/007 同根因) |
| B1 案例清理 | 80% | ✅ 部分完成 (P1-B 双向链接补全) |
| B2 社区运营自动化 | 30% | 🟡 接受长期推进 |
| B3 招募宣传 | 50% | ✅ README/Discord 已发布 |
| C1-C7 工具独立化 | 70% | ✅ 7/11 工具已有独立 CLI (v2.15 smoke 测试覆盖 28 命令) |

**最终决策**：
- 关闭 ADR-011 大框架
- 已完成部分归入 v2.16.0 changelog
- A 轨道并入 ADR-005/007 废弃理由
- B/C 轨道作为未来 P2/P3 候选

## 影响

### 正面

- ADR.md 索引 19 个 → 16 个活跃 ADR (减少 3 个废弃 + 1 个已通过)
- 新增 ADR 不会被陈旧条目掩盖
- 长期未决 ADR 监控信号：3 个 ADR (5/7/11) 提议超 60 天 → 流程需 review

### 负面

- 4 个 ADR 的方案未完全实施（部分功能未交付）
- 后续若需要"AI 导航"能力需重新评估

## 经验

- 提议 ADR 后 30 天内无进展应主动关闭或降级
- 向量 RAG/embedding 类方案在小型知识库（< 500 文档）ROI 偏低
- 轻量级方案（关键词 + alias 映射）可覆盖 80% 场景

## 相关 ADR

- ADR-005: AI 导航系统架构 (已废弃)
- ADR-007: M4 AI 导航系统设计 (已废弃)
- ADR-008: 生产级工作流 (已通过)
- ADR-011: Phase 18 (已拆分关闭)
- ADR-012: 向量 RAG 不作为核心 (本 ADR 部分理由同源)

## 元数据

- 提议：jcode
- 评审：2026-08-29 (v2.16.0 治理收尾)
- 通过：2026-08-29
- 实施：ADR.md 索引更新 + 4 个 ADR 状态字段更新
