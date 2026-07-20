# Agent 定义索引

本项目中的所有 agent 定义，按职责分类索引。

> **治理标准**: 遵循 `GOVERNANCE.md` 第 1 节 Agent 定义格式和第 3 节质量门禁
> **模板**: `docs/agent-dev/agent-prompt-template.md`

---

## 📋 Agent 目录总览

| Agent | 中文名称 | 职责 | 状态 | 定义位置 |
|-------|----------|------|------|----------|
| `knowledge-curator` | 知识策展人 | 维护知识库结构、案例收集、文档质量 | ✅ 已定义 | `agents/knowledge-curator.md` |
| `governance-auditor` | 治理审计员 | 自动化审计代码质量、安全、治理合规 | ✅ 已定义 | `agents/governance-auditor.md` |
| `workflow-optimizer` | 工作流优化师 | 分析效率数据、优化 AI 协作工作流、推荐工具组合 | ✅ 已定义 | `agents/workflow-optimizer.md` |
| `community-catalyst` | 社区催化剂 | 管理贡献流程、案例验证、贡献者激励 | ✅ 已定义 | `agents/community-catalyst.md` |
| `context-sync` | 上下文同步 | 自动维护 CONTEXT.md、ADR.md、同步项目状态 | ✅ 已实现 | `examples/ai-context-sync/src/orchestrator.py` |
| `multi-agent-orch` | 多 Agent 编排器 | 模拟团队开发：PM/Architect/Coder/Reviewer 协作 | ✅ 已实现 | `examples/multi-agent-orch/src/orchestration/` |
| `self-correction-loop` | 自我修正循环 | AI 代码质量保证：验证→重试→修正闭环 | ✅ 已实现 | `examples/self-correction-loop/src/strategies/` |
| `ai-task-prioritizer` | 任务优先级工具 | CLI 任务优先级排序，TDD + AI 驱动 | ✅ 已实现 | `examples/ai-task-prioritizer/prioritizer.py` |

---

## 🎯 核心治理 Agent (P0 - 已定义)

### 1. knowledge-curator (知识策展人)
**职责**: 维护知识库结构完整性、收集真实案例、审核文档质量、更新 INDEX/MOC
**作用域**: `docs/`, `case-studies/`, `INDEX.md`, `MOC.md`
**核心指令**:
- 每周扫描 `case-studies/` 目录，验证案例格式完整性（背景/过程/对比/洞察/场景）
- 运行 `tools/scripts/link_auditor.py` 检查文档断链，生成修复报告
- 运行 `tools/scripts/validate_case_study.py` 验证新提交案例
- 更新 `INDEX.md` 案例表格和 `MOC.md` 知识覆盖率统计
- 执行 `tools/scripts/update_ai_tool_matrix.py` 同步工具矩阵最新版本

### 2. governance-auditor (治理审计员)
**职责**: 自动化审计代码质量、安全漏洞、治理标准合规性
**作用域**: 全项目代码、配置、CI/CD
**核心指令**:
- 执行 `ruff check` + `ruff format --check` 验证代码风格
- 运行 `mypy` 类型检查（配置 `pyproject.toml`）
- 执行 `pytest` 测试套件，要求覆盖率 ≥ 70%
- 运行 `tools/scripts/audit_to_pr.py` 生成审计报告并创建 PR
- 检查 `GOVERNANCE.md` 质量门禁：无 `unwrap()`/`expect()`、无 `as any`、错误处理完整

### 3. workflow-optimizer (工作流优化师)
**职责**: 分析 AI 协作效率数据、优化全周期工作流、推荐工具组合
**作用域**: `docs/efficiency/`, `examples/`, `case-studies/`
**核心指令**:
- 分析 `case-studies/*.md` 中的效率提升数据，生成趋势报告
- 对比 `docs/tools/ai-tool-matrix.md` 推荐与实际案例使用工具的差异
- 运行 `examples/ai-context-sync` 验证全周期工作流有效性
- 更新 `docs/efficiency/full-cycle-workflow.md` 避坑指南
- 维护 `docs/efficiency/metrics-framework.md` 度量体系

### 4. community-catalyst (社区催化剂)
**职责**: 管理贡献流程、验证社区案例、设计贡献者激励机制
**作用域**: `.github/`, `CONTRIBUTING.md`, `FEEDBACK.md`, `case-studies/`
**核心指令**:
- 监控 GitHub Issues/PRs，按标签分流（案例/工具/方法论/问题）
- 验证社区提交案例：运行 `validate_case_study.py`、检查真实性、效率数据
- 执行 `tools/scripts/adr_generator.py` 从 PR 生成 ADR
- 更新 `ROADMAP.md` 社区里程碑进度
- 维护贡献者排行榜和激励记录

---

## ⚙️ 已实现参考 Agent (验证方法论用)

### 5. context-sync (上下文同步)
**定位**: 参考实现 | 验证 `docs/efficiency/full-cycle-workflow` 和 `learning/prompt-engineering`
**实现**: `examples/ai-context-sync/src/orchestrator.py` - `ContextSyncOrchestrator`
**核心能力**:
- 自动维护 `CONTEXT.md`（项目状态、决策、计划）
- 生成 `ADR.md` 架构决策记录
- 规范审计：检查代码是否符合项目规范
- 多 LLM 支持：OpenAI/Claude/Gemini/Ollama/系统自动检测
- MCP Server 集成（opencode 配置见 `opencode.json`）

### 6. multi-agent-orch (多 Agent 编排器)
**定位**: 代码示例 | 模拟团队开发：PM/Architect/Coder/Reviewer 角色分工
**实现**: `examples/multi-agent-orch/src/orchestration/`
**核心能力**:
- 4 角色 Agent：PM(需求分析)、Architect(架构设计)、Coder(实现)、Reviewer(审查)
- 协作协议：结构化消息传递、共享上下文、迭代优化
- 演示文件：`demo.py`

### 7. self-correction-loop (自我修正循环)
**定位**: 代码示例 | AI 代码质量保证：验证→重试模式
**实现**: `examples/self-correction-loop/src/strategies/`
**核心能力**:
- 多策略修正：语法修复、类型修复、逻辑修复、测试驱动修复
- 运行器：`runner.py` 执行修正循环
- 结果追踪：`results.py` 记录修正历史

### 8. ai-task-prioritizer (任务优先级工具)
**定位**: 代码示例 | CLI 任务优先级排序，TDD + AI 驱动开发
**实现**: `examples/ai-task-prioritizer/prioritizer.py`
**核心能力**:
- LLM 评分任务优先级（影响力、紧急度、工作量）
- 交互式任务管理：`main.py`
- 设计文档：`DESIGN.md`、PRD: `PRD.md`

---

## 📂 Agent 定义文件结构

```
ai_developer_growth/
├── AGENTS.md                    # 本文件 - 索引
├── agents/                      # Agent 定义目录 (待创建)
│   ├── knowledge-curator.md
│   ├── governance-auditor.md
│   ├── workflow-optimizer.md
│   └── community-catalyst.md
├── examples/                    # 参考实现
│   ├── ai-context-sync/         # context-sync
│   ├── multi-agent-orch/        # multi-agent-orch
│   ├── self-correction-loop/    # self-correction-loop
│   └── ai-task-prioritizer/     # ai-task-prioritizer
└── docs/agent-dev/              # 开发规范
    ├── agent-prompt-template.md
    ├── prompt-standards.md
    ├── workflow-standards.md
    ├── quality-gates.md
    └── context-management.md
```

---

## ✅ 创建 Agent 检查清单

新增 agent 时必须完成：

- [ ] **命名**: kebab-case，如 `feature-builder`
- [ ] **描述**: 一句话，明确职责和作用域
- [ ] **指令**: 具体、可验证，含工具名/文件路径/函数名
- [ ] **工具**: 最小权限原则，不超过 10 个
- [ ] **约束**: 明确禁止行为
- [ ] **Gate 1 通过**: Prompt 设计审查（人工）
- [ ] **Gate 2 通过**: 实现代码审查（Linter + 类型检查 + 人工）
- [ ] **Gate 3 通过**: 自动化审计（CI/CD）
- [ ] **Gate 4 通过**: 资产更新（更新 AGENTS.md、CONTEXT.md、ADR.md）
- [ ] **索引更新**: 在本文件添加记录

---

## 🔗 相关文档

- [[GOVERNANCE|通用治理标准]] - Agent 定义格式、5步闭环、4道门禁
- [[docs/agent-dev/prompt-standards|Prompt 编写规范]] - 高质量 Prompt 设计原则
- [[docs/agent-dev/workflow-standards|开发流程规范]] - Agent 开发全流程标准
- [[docs/agent-dev/quality-gates|质量门禁]] - 各阶段质量检查标准
- [[docs/agent-dev/context-management|上下文管理]] - CONTEXT/ADR/AGENTS 维护规范
- [[CONTRIBUTING|贡献指南]] - 案例提交、工具推荐、方法论改进流程

---

*本索引随 Agent 新增/修改时更新。最后更新: 2026-07-21*