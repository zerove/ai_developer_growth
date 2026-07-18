# AI Developer Growth: 领域术语表 (Ubiquitous Language)

> 本项目的核心领域术语定义，确保所有文档和 Agent 使用一致的语言。

---

## 核心概念

| 术语 | 英文 | 定义 | 使用场景 |
|------|------|------|----------|
| 知识库 | Knowledge Base | 以文档和案例为核心的知识资产集合，非代码产品 | 项目定位、README |
| 方法论 | Methodology | 可复用的实践模式和工作流程 | docs/efficiency/ |
| 案例研究 | Case Study | 真实项目的 AI 协作开发记录，包含效率数据 | case-studies/ |
| 参考实现 | Reference Implementation | 用于验证方法论的代码实现，非核心产品 | examples/ |

---

## 治理术语

| 术语 | 英文 | 定义 | 来源 |
|------|------|------|------|
| 质量门禁 | Quality Gate | 开发流程中的质量检查关卡，必须通过才能继续 | GOVERNANCE.md |
| 5 步闭环 | 5-Step Lifecycle | 需求分析→Prompt 设计→实现编码→自动化审计→资产更新 | GOVERNANCE.md |
| 资产更新 | Asset Update | 开发完成后更新文档、ADR、CONTEXT 等项目资产 | GOVERNANCE.md |
| 最小权限 | Least Privilege | Agent 仅获得完成任务所需的最少工具权限 | prompt-standards.md |
| 上下文管理 | Context Management | 维护 CONTEXT.md、ADR.md、AGENTS.md 等状态文件 | context-management.md |

---

## Agent 术语

| 术语 | 英文 | 定义 |
|------|------|------|
| Agent 定义 | Agent Definition | 描述 Agent 职责、工具、约束的结构化文档 |
| Prompt 设计 | Prompt Design | 编写 Agent 指令的过程，强调具体性和可验证性 |
| Agent 协作 | Agent Collaboration | 多个 Agent 按照编排模式共同完成任务 |
| 编排模式 | Orchestration Pattern | Agent 间的协作结构：串行、并行、主从、对等 |

---

## 效率术语

| 术语 | 英文 | 定义 |
|------|------|------|
| 全周期工作流 | Full-Cycle Workflow | 从需求到部署的完整 AI 协作开发流程 |
| 自动化修复 | Automated Bug Fixing | AI 辅助的 Bug 定位→修复→验证流程 |
| 上下文工程 | Context Engineering | 精准传递项目上下文给 AI 的方法论 |
| Token 成本控制 | Token Optimization | 优化 AI 调用成本的策略和技术 |
| 多 Agent 编排 | Multi-Agent Orchestration | 协调多个 Agent 协作的模式和实践 |

---

## 工具术语

| 术语 | 英文 | 定义 |
|------|------|------|
| AI 工具矩阵 | AI Tool Matrix | 模型、IDE、Agent 的对比选型框架 |
| MCP 服务器 | MCP Server | Model Context Protocol 服务器，提供工具和资源 |
| 上下文同步 | Context Sync | 自动维护项目 CONTEXT.md 的过程 |
| 架构决策记录 | ADR (Architecture Decision Record) | 记录关键架构决策的文档 |

---

## 学习术语

| 术语 | 英文 | 定义 |
|------|------|------|
| AI 学习法 | AI Learning Method | 用 LLM 快速攻克新领域的学习范式 |
| 知识内化 | Knowledge Internalization | 将 AI 生成的知识转化为底层能力的过程 |
| Prompt 工程 | Prompt Engineering | 编写高质量提示词的技术和方法 |

---

## 术语关系图

```
知识库 (Knowledge Base)
├── 方法论 (Methodology)
│   ├── 全周期工作流
│   ├── 自动化修复
│   └── 上下文工程
├── 案例研究 (Case Study)
│   └── 效率数据 (Efficiency Metrics)
├── 参考实现 (Reference Implementation)
│   └── MCP 服务器
└── 治理 (Governance)
    ├── 质量门禁
    ├── 5 步闭环
    └── Agent 定义
```

---

*本表随新增术语时更新。最后更新: 2026-07-18*
