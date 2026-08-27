# Agent 定义索引

> **JCode 工作流配置（重要）**: 本项目的完整 JCode 工作流配置在 `.jcode/AGENTS.md`
> （合并自 PROJECT.md / USAGE.md / DEV_WORKFLOW.md / SWARM.md）。
> **启动 JCode 会话后，先读取 `.jcode/AGENTS.md` 再执行任务**，其中包含：
> 语言规则（默认中文）、5 个 Agent Skill 与入口脚本（`.jcode/scripts/*.py`）、
> hooks 执行引擎（`hooks_runner.py`）、开发/分支/提交规范、AI-Native 工作流。
> 简版规则摘要：
> - 回复、注释、文档、提交信息默认中文；代码标识符与技术术语保留英文
> - 提交信息格式：`type(scope): 中文描述`（允许类型：feat/fix/refactor/docs/test/...）
> - 代码风格：Python 走 ruff + mypy + pytest 门禁
> - 分支策略：`main` / `feature/*` / `fix/*`

本项目中的所有 agent 定义，按职责分类索引。

> **治理标准**: 遵循 `GOVERNANCE.md` 第 1 节 Agent 定义格式和第 3 节质量门禁
> **模板**: `docs/agent-dev/agent-prompt-template.md`

---

## 📋 Agent 目录总览

| Agent | 中文名称 | 职责 | 状态 | 定义位置 |
|-------|----------|------|------|----------|
| `knowledge-curator` | 知识策展人 | 维护知识库结构、案例收集、文档质量 | ✅ 已定义 | `agents/knowledge-curator.md` |
| `governance-auditor` | 治理审计员 | 自动化审计代码质量、安全、治理合规 | ✅ 已定义 (v1.1) | `agents/governance-auditor.md` |
| `governance-docs-validator` | 治理文档验证器 | 验证治理层文档、索引引用、交叉引用 | ✅ 已定义 (v1.0) | `.jcode/skills/governance-docs-validator.md` |
| `workflow-optimizer` | 工作流优化师 | 分析效率数据、优化 AI 协作工作流、推荐工具组合 | ✅ 已定义 | `agents/workflow-optimizer.md` |
| `community-catalyst` | 社区催化剂 | 管理贡献流程、案例验证、贡献者激励 | ✅ 已定义 | `agents/community-catalyst.md` |
| `context-sync` | 上下文同步 | 自动维护 CONTEXT.md、ADR.md、同步项目状态 | ✅ 已集成 (v1.0) | `agents/context-sync.md` / `.jcode/scripts/context_sync.py` |
| `multi-agent-orch` | 多 Agent 编排器 | 模拟团队开发：PM/Architect/Coder/Reviewer 协作 | ✅ 已集成 (v1.0) | `agents/multi-agent-orch.md` / `.jcode/scripts/multi-agent-orch.py` |
| `self-correction-loop` | 自我修正循环 | AI 代码质量保证：验证→重试→修正闭环 | ✅ 已集成 (v1.0) | `agents/self-correction-loop.md` / `.jcode/scripts/self-correction-loop.py` |
| `ai-task-prioritizer` | 任务优先级工具 | CLI 任务优先级排序，TDD + AI 驱动 | ✅ 已实现 | `examples/ai-task-prioritizer/prioritizer.py` |
| `hooks-runner` | 统一 Hook 运行器 | 统一 lint/typecheck/test/security/quality-gate/governance 入口 | ✅ 已实现 | `tools/scripts/hooks_runner.py` |
| `rules-engine` | 规则引擎 | 语言无关的代码质量检查引擎（反模式/命名/阈值/AST） | ✅ 已实现 | `tools/scripts/rules_engine/` |
| `jcode-ai-native-workflow` | AI-Native 工作流主管道 | 集成核心支柱的全生命周期研发自动化流水线 | ✅ 已实现 | `tools/scripts/jcode_ai_native_workflow.py` |

---

## 🎯 核心治理 Agent (P0 - 已定义)

### 1. knowledge-curator (知识策展人)
**职责**: 维护、收集真实案例、审核文档质量、更新 docs/MOC.md
**作用域**: `docs/`, `case-studies/`, `docs/MOC.md`:
- 每周扫描 `case-studies/` 目录，验证案例格式完整性（背景/过程/对比/洞察/场景）
- 运行 `tools/scripts/link_auditor.py` 检查文档断链，生成修复报告
- 运行 `tools/scripts/validate_case_study.py` 验证新提交案例
- 更新 `docs/MOC.md`
- 执行 `tools/scripts/update_ai_tool_matrix.py` 同步

### 2. governance-auditor (治理审计员 v1.1)
**职责**: 自动化审计代码
**作用域**: 全项目代码、配置、CI/CD、治理层文档
**核心指令**:
- 执行 `ruff check` + `ruff format --check` 验证代码风格
- 运行 `mypy` 类型检查（配置 `pyproject.toml`）
- 执行 `pytest` 测试套件，要求覆盖率 ≥ 60%
- 运行 `tools/scripts/audit_to_pr.py` 生成审计报告并创建 PR
- 检查 `GOVERNANCE.md` 质量门禁：无 `unwrap()`/`expect()`、无 `as any`
- **v1.1 新增**: 验证15个治理层文档格式完整性
- **v1.1 新增**: 检查 AI-SDLC 合规性
- **v1.1 新增**: 审计幻觉风险（代码不安全模式 + 文档绝对化声明）

### 3. governance-docs-validator (治理文档验证器 v1.0)
**职责**: 验证治理层文档、索引引用、交叉引用同步
**作用域**: `docs/efficiency/ai-*.md`, `GOVERNANCE.md`, `docs/MOC.md`, `CLAUDE.md`
**核心指令**:
- 运行 `python .jcode/scripts/governance-docs-validator.py validate` 验证文档格式
- 运行 `python .jcode/scripts/governance-docs-validator.py check-index` 检查索引引用
- 运行 `python .jcode/scripts/governance-docs-validator.py sync-refs` 同步交叉引用
- 验证 frontmatter 完整性：category、tags、difficulty
- 检查导航部分和相关文档引用

### 4. workflow-optimizer (工作流优化师)
**职责**: 分析 AI 协作效率数据、优化全周期工作流、推荐工具组合
**作用域**: `docs/efficiency/`, `examples/`, `case-studies/`
**核心指令**:
- 分析 `case-studies/*.md` 中的效率数据与洞察
- 对比 `docs/tools/ai-tool-matrix.md` 推荐与实际案例
- 运行 `examples/ai-context-sync` 验证全周期工作流
- 更新 `docs/efficiency/full-cycle-workflow.md` 避坑指南
- 维护 `docs/efficiency/metrics-framework.md` 度量体系

### 5. community-catalyst (社区催化剂)
**职责**: 管理贡献流程、验证社区案例、设计贡献者激励机制
**作用域**: `.github/`, `CONTRIBUTING.md`, `FEEDBACK.md`, `case-studies/`
- 监控 GitHub Issues/PRs，按标签分流（案例/工具/方法论/问题）
- 验证社区提交案例：运行 `validate_case_study.py`、检查真实性、效率数据
- 执行 `tools/scripts/adr_generator.py` 从 PR 生成 ADR
- 更新 `ROADMAP.md` 社区里程碑进度
- 维护激励记录

---

## ⚙️ 核心技能 Agent (P1 - 已集成到 Hooks 流程)

### 6. context-sync (上下文同步 v1.0)
**职责**: 自动维护 CONTEXT.md、ADR.md、同步项目状态，架构决策防护，规范审计
**作用域**: 全项目 Git 历史、CONTEXT.md、ADR.md、SPEC.md
**核心指令**:
- 运行 `python .jcode/scripts/context_sync.py sync --project-root .` 分析 Git 变更，自动更新 CONTEXT.md 和 ADR.md
- 运行 `python .jcode/scripts/context_sync.py validate --context-file CONTEXT.md --adr-file ADR.md` 验证文档结构完整性
- 运行 `python .jcode/scripts/context_sync.py audit --spec-file SPEC.md` 检查代码/文档规范合规（硬编码密钥、eval/exec、SQL注入、裸露except等）
- 架构防护：检查设计文档偏移（TODO/FIXME、过于简短、缺少子任务分解）
- 演化分析：运行 `python .jcode/scripts/context_sync.py evolve` 检查规范演化机会
**Hooks 集成**: on_commit (sync), on_merge (sync), on_pr (audit), scheduled (validate/audit)

### 7. multi-agent-orch (多 Agent 编排器 v1.0)
**职责**: 模拟团队开发：PM/Architect/Coder/Reviewer 角色分工协作，结构化消息协议，迭代优化
**作用域**: 设计类需求、规格文档、架构决策
**核心指令**:
- 接收用户自然语言需求描述
- PM 阶段生成 PRD（目标、需求、成功标准）
- Architect 阶段生成技术设计（架构、API、实施计划、子任务分解 JSON）
- Coder-Reviewer 循环：Coder 生成代码 → Reviewer 审查 PASS/FAIL → FAIL 反馈 FIX 进入下一轮
- 支持模式：waterfall（串行瀑布）、fanout（并行扇出）
- 最大迭代次数默认 3，可配置
**Hooks 集成**: on_pr (design 标签或 design/spec 目录变更)

### 8. self-correction-loop (自我修正循环 v1.0)
**职责**: AI 代码质量保证闭环：验证 → 重试 → 修正，自动修复测试失败
**作用域**: 失败的测试文件、CI/CD 流程
**核心指令**:
- 运行 `python .jcode/scripts/self-correction-loop.py validate --target <file> --tests <dir>` 验证当前测试状态
- 运行 `python .jcode/scripts/self-correction-loop.py run --target <file> --tests <dir> --max-attempts 3` 启动测试→修复→验证闭环
- 策略链：retry（重试）→ pattern（模式匹配：off-by-one、missing-import、zero-division）→ llm（大模型修复，回退 Mock）
- 输出结构化 JSON 报告：成功/失败、尝试次数、使用策略、耗时、修正前后代码对比
**Hooks 集成**: on_pr (测试失败时自动触发)

---

## ⚙️ 已实现参考 Agent (验证方法论用)

### 9. ai-task-prioritizer (任务优先级工具)
**定位**: 代码示例 | CLI 任务优先级排序，TDD + AI 驱动开发
**实现**: `examples/ai-task-prioritizer/prioritizer.py`
**核心能力**:
- LLM 评分任务优先级（影响力、紧急度、工作量）
- 交互式任务管理：`main.py`
- 设计文档：`DESIGN.md`、PRD: `PRD.md`

### 10. hooks-runner (统一 Hook 运行器)
**定位**: 核心基础设施 | 统一执行引擎
**实现**: `tools/scripts/hooks_runner.py`
**核心能力**: 解析 `.jcode/hooks.json`，按条件执行 skills

### 11. rules-engine (规则引擎)
**定位**: 核心基础设施 | 语言无关质量检查
**实现**: `tools/scripts/rules_engine/`
**核心能力**: 反模式检测、命名规范、复杂度阈值、安全模式、AST 分析

### 12. jcode-ai-native-workflow (AI-Native 工作流主管道)
**定位**: 核心基础设施 | 全生命周期自动化
**实现**: `tools/scripts/jcode_ai_native_workflow.py`
**核心能力**: 集成 Sense/Design/Implement/Audit/Sync 五阶段

---

## 📂 Agent 定义文件结构

```
ai_developer_growth/
├── AGENTS.md                    # 本文件 - 索引
├── agents/                      # Agent 定义目录
│   ├── knowledge-curator.md
│   ├── governance-auditor.md
│   ├── workflow-optimizer.md
│   ├── community-catalyst.md
│   ├── context-sync.md              # NEW: 已集成
│   ├── multi-agent-orch.md          # NEW: 已集成
│   └── self-correction-loop.md      # NEW: 已集成
├── .jcode/
│   ├── hooks.json               # Hooks 配置（含新技能）
│   ├── scripts/                 # Skill 入口脚本
│   │   ├── governance-auditor.py
│   │   ├── governance-docs-validator.py
│   │   ├── knowledge-curator.py
│   │   ├── workflow-optimizer.py
│   │   ├── community-catalyst.py
│   │   ├── hooks_runner.py
│   │   ├── context_sync.py            # NEW
│   │   ├── multi-agent-orch.py        # NEW
│   │   └── self-correction-loop.py    # NEW
│   └── skills/                  # Skill 定义
│       ├── governance-docs-validator.md
│       └── ...
├── tools/scripts/               # 核心工具脚本
│   ├── hooks_runner.py
│   └── rules_engine/
│       ├── __init__.py
│       ├── models.py
│       ├── rule_loader.py
│       ├── anti_pattern_checker.py
│       ├── naming_checker.py
│       ├── complexity_checker.py
│       ├── security_patterns.py
│       └── checker.py
├── examples/                    # 参考实现
│   ├── ai-context-sync/
│   ├── multi-agent-orch/
│   ├── self-correction-loop/
│   └── ai-task-prioritizer/
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
- [ ] **工具**: 最小 10 个
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
- [[CONTRIBUTING|贡献指南]] - 案例流程

---

*本索引随 Agent 新增/修改时更新。最后更新: 2026-08-22*
