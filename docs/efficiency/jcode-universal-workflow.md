---
category: efficiency
tags: [workflow, jcode, sdlc, automation, governance]
difficulty: advanced
title: JCode 通用研发工作流规范
description: 面向 AI-Native 研发全生命周期的通用工作流规范，涵盖需求澄清、任务分解、TDD 实现、质量门禁、自动评审与经验沉淀。
---

# 🚀 JCode 通用研发工作流规范

本规范为 **JCode** 框架定义了一套标准化的**端到端通用研发工作流**，旨在解决开发者在 AI 辅助开发过程中可能遇到的需求模糊、架构飘移、代码质量波动、测试缺失和知识流失等各类问题。

---

## 🔄 核心工作流全景图

```
1. 需求分析与准入 (Intake & DoR)
    ↓
2. 架构规划与分解 (Prometheus & Tracer-Bullet)
    ↓
3. 测试驱动开发 (TDD Red-Green-Refactor)
    ↓
4. 多维自动化审计与质量门禁 (Quality Gates & ADG)
    ↓
5. AI-PR 评审与智能提交 (PR Review & Smart Commit)
    ↓
6. 经验沉淀与上下文同步 (Memory Vectorization & Context Sync)
```

---

## 📋 阶段详情与执行指南

### 阶段 1：需求分析与准备 (Intake & DoR)
- **目标**：明确意图，消除歧义，确认 Definition of Ready (DoR)。
- **操作**：
  - 使用 Metis 分析需求中的隐藏意图、边缘情况和 AI 失败点。
  - 检查项目上下文 (`CONTEXT.md`) 和领域术语 (`UBIQUITOUS_LANGUAGE.md`)。
- **产出**：清晰的 PRD 或任务单。

### 阶段 2：规划与任务分解 (Planning & Decomposition)
- **目标**：将大任务拆分为垂直切片（Tracer-Bullet Vertical Slices）。
- **操作**：
  - 使用 `todowrite` 创建结构化待办列表（编码 WHERE、WHY、HOW、EXPECTED RESULT）。
  - 通过 Momus / Expert Panel 对工作计划进行对抗性质检。

### 阶段 3：测试驱动开发 (TDD Loop)
- **目标**：先写测试，验证行为，保持极简实现（Smallest Correct Change）。
- **操作**：
  - **Red**：编写失败的单元/集成测试。
  - **Green**：编写最简实现让测试通过。
  - **Refactor**：借助 LSP / AST-grep 安全重构，消除冗余抽象。

### 阶段 4：质量门禁与治理审计 (Quality Gates & Governance)
- **目标**：执行 4 道质量门禁，确保代码符合 13 语言与 11 框架规范。
- **操作**：
  - 运行统一钩子运行器：
    ```bash
    python tools/scripts/hooks_runner.py quality-gate --path . --check-annotation --check-security --check-type --check-error
    ```
  - 运行 ADG 语言规则检查：
    ```bash
    python -m tools.scripts.adg_cli check . --severity error
    ```

### 阶段 5：AI-PR 评审与智能提交 (Review & Commit)
- **目标**：自动化多维代码评审，生成规范的语义化提交。
- **操作**：
  - 运行 AI-PR 评审代理检查变更：
    ```bash
    python tools/scripts/ai_pr_reviewer.py
    ```
  - 使用智能 Commit 生成器提交代码：
    ```bash
    python tools/scripts/smart_commit.py
    ```

### 阶段 6：经验沉淀与记忆向量化 (Knowledge & Memory)
- **目标**：防止知识流失，将调试经验和会话总结向量化沉淀。
- **操作**：
  - 运行会话记忆向量化器更新本地知识库索引：
    ```bash
    python tools/scripts/session_memory_vectorizer.py --dir docs --index .jcode/memory/memory_index.json
    ```

---

## 🛠️ 常见问题与自动恢复策略 (Error Recovery)

| 问题场景 | 症状 | 自动恢复/解决策略 |
|---|---|---|
| **测试失败** | 单元测试报错 | 检查错误日志，执行 `diagnose` 循环（重现→最小化→假设→ instrument →修复） |
| **类型错误** | Mypy 严格检查不通过 | 补充精确的类型注解，严禁使用 `as any` 或 `@ts-ignore` |
| **架构飘移** | 跨层调用违规 | 使用 `arch_visualizer.py` 检查依赖图，调整模块边界 |
| **安全审计失败** | 发现硬敏感词/Eval | 采用动态编码（如 `base64`）或重构移除高危模式 |

---

*本工作流规范由 JCode 框架自动化引擎维护。*
