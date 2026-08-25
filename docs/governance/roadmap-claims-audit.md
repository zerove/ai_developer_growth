---
title: 路线图声明审计
description: ROADMAP 文档声明与实际状态对照审计
category: 治理层
tags: [审计, 路线图, 治理]
difficulty: 进阶
updated: 2026-08-25
---

# ROADMAP 声称真实性清单

> 生成日期: 2026-08-24
> 方法: 逐条核对 `ROADMAP.md` 中 `[x]` 勾选项与仓库实际状态（文件存在性、数量统计、git 历史）。
> 目的: 落实"门禁配置必须对齐现实"原则，区分 **属实**（可验证）、**存疑**（部分成立或无法直接验证）、
> **虚构/过期**（与仓库现状不符）三类，为后续 ROADMAP 修订提供依据。

## 一、属实（有仓库证据支撑）

| ROADMAP 声称 | 核实证据 | 结论 |
|---|---|---|
| 核心方法论文档（认知/学习/效率/工具/治理） | `docs/` 下 261 篇 markdown，目录结构与声称分层一致 | ✅ 属实（数量已超声称的 253，需更新数字） |
| 工具矩阵 | `docs/tools/ai-tool-matrix.md` 存在且由 `tools/scripts/update_ai_tool_matrix.py` 维护 | ✅ 属实 |
| 代码示例 | `examples/` 实际 10 个子项目（ai-context-sync、ai-task-prioritizer、multi-agent-orch、self-correction-loop 等） | ✅ 属实 |
| 通用治理框架 ai-dev-framework 含 adg CLI | `ai-dev-framework/` 存在，`.venv/bin/adg` 可执行入口真实安装 | ✅ 属实 |
| 案例库 43 个案例 | `case-studies/` 实际 46 个 `.md` 文件（已超声称） | ✅ 属实（数字过期，实际更多） |
| ADR 补充 ADR-001~009 + 清理 | `docs/adr/` 存在 001~009 及 ADR-010、ADR-011 | ✅ 属实 |
| 治理规范 26 语言 + 9 框架 + 3 领域 = 38 份 | `ai-dev-framework/languages` 26 个；`frameworks` 9 个；`domains` 3 个，合计 38 | ✅ 属实 |
| MkDocs 网站（Material 主题）+ GitHub Pages 部署 | `mkdocs.yml` 存在；`.github/workflows/deploy-docs.yml` 存在 | ✅ 属实 |
| 用户行为追踪 tracking.js + analyze_tracking.py | `docs/assets/javascripts/tracking.js` 与 `tools/scripts/analyze_tracking.py` 均存在 | ✅ 属实 |
| 全周期工作流 / 自动化修复等效率文档 | `docs/efficiency/full-cycle-workflow.md`、`metrics-framework.md` 等存在 | ✅ 属实 |
| 能力等级模型 L1-L5 | 见 docs 相关能力模型文档（knowledge 层引用一致） | ✅ 属实 |

## 二、存疑（部分成立或依赖运行时验证）

| ROADMAP 声称 | 核实情况 | 建议 |
|---|---|---|
| 测试覆盖率 "2513 测试全通过 (2026-08-04)" | 当前收集 2424+ 用例且持续增长（本轮新增多个回归测试），数字必然过期；"84%→88%" 为历史快照无法从静态文件复核 | 改为"以 CI 最近一次绿色运行为准"，去掉硬编码数字或标注日期 |
| BM25 + 同义词 + 协同过滤 + 向量 RAG 增强检索 | `examples/ai-navigation/src/hybrid_search.py`、`vector_search.py` 及对应测试存在，功能属实；但"协同过滤推荐"未找到独立实现模块 | 协同过滤单独标注实现位置或移除该词 |
| 对话界面 chat_interface.py / 个性化导师 personalized_mentor.py | 两文件存在于 `examples/ai-navigation/src/`，但属示例代码，非产品级部署 | 标注"示例级实现" |
| 深度文档重写"所有核心文档全部 500+ 字" | 未逐篇验证字数；抽查核心文档达标 | 抽查结论为大概率属实，建议脚本化验证后转"属实" |

## 三、虚构/过期（与仓库现状不符）

| ROADMAP 声称 | 核实情况 | 处理建议 |
|---|---|---|
| "17 个测试，覆盖率 84%"（历史里程碑行） | 与当前 2400+ 测试严重不符，属历史阶段数字未随时间更新 | 标注历史时点或删除误导性行 |
| 案例数固定写 43 | 实际 46 | 更新为最新计数并注明动态统计口径 |
| 文档数固定写 253 | 实际 261 | 同上 |

## 四、结论与后续动作

1. ROADMAP 中绝大多数 `[x]` 声称有真实产物支撑，**无整体虚构问题**；
2. 主要风险是 **数字过期**（文档数/案例数/测试数）与 **个别组件定位夸大**（示例级实现被写成系统能力）；
3. 建议后续：
   - 数字类指标改为引用自动生成报告（如 stats_history.jsonl 或 CI 徽章），避免手工维护过期；
   - 示例级实现统一加"example-level"标注；
   - 本清单随 ROADMAP 修订同步归档至 git 历史。
