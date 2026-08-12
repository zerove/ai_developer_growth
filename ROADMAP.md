# 项目路线图

> 务实、可验证、可执行的进化路径。

---

## 愿景

定义 AI 时代开发者的"新能力模型"，帮助开发者从"代码编写者"升级为"AI 协同的系统架构师"。

**核心原则**: 知识优先，工具为辅，案例验证。

---

## 当前状态 (2026-08-04)

### ✅ 已完成
- [x] **核心方法论文档** - 253 篇文档（认知/学习/效率/工具/治理）
- [x] **工具矩阵** - 模型/IDE/Agent 选型指南（已更新至最新）
- [x] **工程效率文档** - 全周期工作流、自动化 Bug 修复、AI-Native SDLC 11 支柱
- [x] **深度文档重写** - 所有核心文档全部 500+ 字
- [x] **代码示例** - 10 个完整示例（含测试和文档）
- [x] **通用治理框架** - ai-dev-framework（已打包发布，含 adg CLI）
- [x] **案例库扩充** - 43 个案例（含 AI-Native 主管道执行、治理自审计）
- [x] **ADR 补充** - 10 条架构决策记录 (ADR-001 ~ ADR-009 + 重复编号清理)
- [x] **治理规范** - 26 语言 + 9 框架 + 3 领域 = 38 份规范
- [x] **能力等级模型** - L1-L5 五级能力定义
- [x] **增强检索** - BM25 算法 + 同义词扩展 + 协同过滤 + 向量 RAG
- [x] **测试覆盖率** - 2513 测试 (2026-08-04 实测全通过)

### ✅ 已完成
- [x] **内容完善** - 253 篇文档 (目标 200，超额完成)
- [x] **案例库扩充** - 43 个案例 (目标 35，超额完成)
- [x] **元数据标签** - 已添加
- [x] **文档结构优化** - 已完成

**Phase 2: 检索优化 (2026 Q4)**
- [x] 优化 TF-IDF 算法 (BM25)
- [x] 增加同义词库 (中英文技术术语)
- [x] 用户行为追踪 (tracking.js + analyze_tracking.py)
- [x] 协同过滤推荐

**Phase 3: Web 界面 (2027 Q1)**
- [x] MkDocs 网站搭建 (Material 主题, nav 修复)
- [x] 搜索界面 (BM25 + 同义词 + 协同过滤)
- [x] GitHub Pages 自动部署 (deploy-docs.yml)
- [x] 用户行为追踪集成

**Phase 4: AI 增强 (2027 Q2, 视需求)**
- [x] 向量数据库集成 (sentence-transformers + cosine similarity)
- [x] RAG 引擎优化 (BM25 + 向量混合搜索 RRF 融合)
- [x] 对话界面 (chat_interface.py - CLI 问答系统)
- [x] 个性化导师 (personalized_mentor.py - 五维能力评估 + 学习计划)

---

## 详细计划

见 `docs/NEXT_STEPS.md`

---

## 里程碑

### M1: 知识体系完善 ✅ 已完成
**目标**: 核心文档齐全，可独立阅读。

- [x] 认知层: 产品思维、独立开发、市场发布（6 篇）
- [x] 学习层: AI 学习法、知识内化、Prompt 工程（3 篇）
- [x] 效率层: 全周期工作流、自动化修复（18 篇）
- [x] 工具层: 工具矩阵、IDE 实践（2 篇）
- [x] 治理层: 26 语言规范 + 9 框架规范 + 3 领域规范
- [x] ADR 补充: 4 条架构决策记录

### M2: 案例库扩充 ✅ 已完成
**目标**: 10+ 真实案例，覆盖不同场景。

- [x] 案例收集: 11 个案例（目标 10+）
- [x] 案例标准化: 统一格式（背景/过程/对比/洞察/场景）
- [x] 案例完整度: 全部含关键洞察和适用场景
- [ ] 案例验证: 社区尝试并反馈（待 M3 启动）

### M3: 社区启动 ✅ 基础完成
**目标**: 10+ 活跃贡献者。

- [x] 贡献者流程优化
- [x] 案例提交流程上线
- [x] 工具评测机制
- [ ] 活跃贡献者招募（进行中）
- [x] 贡献者激励计划

### M4: 知识产品化 ✅ 原型完成（2026-07）
**目标**: 知识库可交互、可个性化。

- [x] RAG 引擎: TF-IDF + 中文分词
- [x] 个性化推荐: 用户画像 + 学习路径
- [x] CLI 工具: build/query/recommend/stats
- [x] 17 个测试，覆盖率 84%

---

## 增长循环

```
观察 (工具/能力变化)
    ↓
实践 (真实项目验证)
    ↓
文档化 (沉淀为知识)
    ↓
社区验证 (他人尝试反馈)
    ↓
迭代 (更新/淘汰)
```

---

## 优先级原则

1. **知识 > 工具**: 文档是核心，工具是验证手段
2. **质量 > 数量**: 10 个优质案例 > 100 个水案例
3. **验证 > 声称**: 每个方法论都需要实践案例支撑
4. **社区 > 单人**: 吸引贡献者比自己写更重要

---

## Phase 5: 交互式学习平台

- [x] Web UI (FastAPI + Jinja2 + SQLite)
  - 用户认证 (register/login/JWT cookie)
  - Dashboard (学习进度/评估/贡献统计)
  - 五维能力评估 (滑块交互 + 推荐)
  - 学习进度追踪 (启动/完成/删除)
  - 文档贡献工作流 (提交/查看/审核)
  - 8 个集成测试

## Phase 6: 自动化治理

- [x] GitHub Actions CI/CD 扩展
  - Example Tests job (8 个示例项目)
  - 测试摘要报告 (GitHub Step Summary)

## Phase 7: 团队协作

- [x] 团队配置隔离 (TeamManager)
  - 创建/删除团队
  - 成员管理 (添加/移除)
  - 团队设置隔离
  - JSON 持久化存储
- [x] 学习路径模板 (LearningPathManager)
  - 3 个预置路径 (入门/实践/领导)
  - 按角色过滤 (frontend/backend/fullstack)
  - 智能推荐 (基于当前/目标等级)
  -
  - 17 个测试

## Phase 8: 生态集成

- [x] VS Code 扩展 (ai-growth-vscode)
  - 技能评估命令
  - 学习进度追踪
  - 推荐系统
  - Webview Dashboard
- [x] Slack Bot (ai-growth-slack)
  - 命令系统 (!growth assess/progress/recommend/help)
  - 用户进度追踪
  - 个性化推荐
  - 7 个测试

## Phase 9: 测试覆盖提升 (2026-07)

- [x] 覆盖率从 84% → 88% (989 → 2513 测试)
- [x] test_rule_tracker / test_plugins / test_rule_loader 补全
- [x] 死代码清理 (validate_language_rules.py 删除 278 行重复函数)
- [x] 模块化重构: rule_marketplace 拆分、fix_heuristics 拆分

## Phase 10: 代码质量优化 + 模块化 (2026-07)

- [x] hooks_runner.py 并行化 (lint+format+typecheck 并行)
- [x] rules_engine 磁盘缓存 (.cache/rules_engine/)
- [x] naming_analyzer / complexity_analyzer / linter_runner / report_generator / fix_applier 新模块
- [x] ADR-002 更新为 Accepted 状态

## Phase 11: 插件系统 (2026-07)

- [x] rules_engine 插件系统 (CheckerPlugin ABC, registry, decorator, discovery)
- [x] rule_marketplace.py 拆分 (rule_catalog + CLI)
- [x] 913 测试全部通过

## Phase 12: 测试补全 + 死代码清理 (2026-07)

- [x] test_rule_tracker (27 tests) / test_plugins (21 tests) / test_rule_loader (29 tests)
- [x] 989 测试全部通过

## Phase 13: 测试覆盖率提升 (2026-07)

- [x] test_rule_catalog_marketplace (41 tests) / test_detect_language (+10) / test_validate_language_rules_extra (19)
- [x] rule_catalog 9%→86% / rule_marketplace 0%→80%
- [x] 1059 测试全部通过

## Phase 14: hooks 拆分 + 集成测试 + 类型安全 (2026-07)

- [x] hooks_runner.py 拆分为 4 模块 (747→260+178+236+131+54 行)
- [x] 34 集成测试 (端到端管道)
- [x] mypy strict errors 19→6
- [x] 2474 测试全部通过

## Phase 15: validate_language_rules 拆分 + CI 增强 (2026-07)

- [x] validate_language_rules.py 拆分为 validators/ 包 (1115→142+731 行)
- [x] CI/CD 增强: coverage fail_under=75, branch coverage, quality gate
- [x] linter_runner 0%→99% / basic_checks 65%→94%
- [x] 1139 测试全部通过

## Phase 16: 实战验证 + 包发布 + 内容精炼 + 文章 (2026-07)

- [x] ai-dev-framework 打包发布 (pyproject + adg CLI + wheel 构建验证)
- [x] 实战验证: quality-gate 审计自身 tools/ 目录, 发现 85 个问题, 修复 4 处 MD5 安全风险
- [x] 实战案例: case-studies/governance-self-audit.md (用自己的药医自己)
- [x] 高质量文章: article-ai-developer-evolution.md

## Phase 17: AI-Native SDLC 生态 + CI/CD 优化与安全强化 (2026-08) 🚧 进行中

- [x] jcode_ai_native_workflow.py 主管道 (集成 11 大支柱)
- [x] autonomous_swarm_engine.py 自主蜂群 + self_evolving_engine.py 自我演化
- [x] ai_native_mcp_server.py MCP 服务器 + ai_native_dashboard.py 仪表板
- [x] DoR gate (dor_checker.py) + TDD 状态机 (tdd_state_machine.py)
- [x] 审计证明账本 (audit_attestation.py) + 范围守护 (architecture_drift_guard.py)
- [x] pip 缓存键 + 测试分片 (4 shards) + 覆盖率合并 job
- [x] 发布工作流 release.yml (tag 触发 + 预发布校验 + twine)
- [x] 示例项目 CI 模板 example-ci-template.yml + 9 个示例项目 .github/ 初始化
- [x] Justfile 统一命令入口 + .markdownlint.json + requirements-lock.txt
- [x] 文档代码片段消毒 mock sk- API keys (防 secret scanning 误报)
- [x] ai_quality_gate 规则自引用假阳性修复 (noqa 注解)
- [ ] 剩余: 发布 v2.4.0 + 社区里程碑

---

*路线图是活的文档，随项目演进持续更新。*
