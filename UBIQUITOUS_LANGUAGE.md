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
| 4 道门禁 | 4 Quality Gates | Gate 1: Prompt 设计 → Gate 2: 实现编码 → Gate 3: 自动化审计 → Gate 4: 资产更新 | GOVERNANCE.md |
| 自动化审计 | Automated Audit | CI/CD 自动执行的代码质量、安全、测试检查 | GOVERNANCE.md |
| Prompt 设计审查 | Prompt Design Review | Gate 1：人工审查 Agent 定义的格式、指令、工具、约束 | GOVERNANCE.md |

---

## Agent 术语

| 术语 | 英文 | 定义 |
|------|------|------|
| Agent 定义 | Agent Definition | 描述 Agent 职责、工具、约束的结构化文档 |
| Prompt 设计 | Prompt Design | 编写 Agent 指令的过程，强调具体性和可验证性 |
| Agent 协作 | Agent Collaboration | 多个 Agent 按照编排模式共同完成任务 |
| 编排模式 | Orchestration Pattern | Agent 间的协作结构：串行、并行、主从、对等 |
| 任务分解 | Task Decomposition | 将复杂任务拆解为独立可执行的原子单元 |
| 并行扇出 | Parallel Fan-out | 同时启动多个独立子任务以最大化吞吐 |
| 会话延续 | Session Continuity | 保持子 Agent 上下文，避免重复探索 |

---

## 效率术语

| 术语 | 英文 | 定义 |
|------|------|------|
| 全周期工作流 | Full-Cycle Workflow | 从需求到部署的完整 AI 协作开发流程 |
| 自动化修复 | Automated Bug Fixing | AI 辅助的 Bug 定位→修复→验证流程 |
| 上下文工程 | Context Engineering | 精准传递项目上下文给 AI 的方法论 |
| Token 成本控制 | Token Optimization | 优化 AI 调用成本的策略和技术 |
| 多 Agent 编排 | Multi-Agent Orchestration | 协调多个 Agent 协作的模式和实践 |
| 度量体系 | Metrics Framework | 量化 AI 效果的三维平衡计分卡 + 自动化采集 |
| 迁移策略 | Legacy AI Migration | 引入 AI 的五阶段渐进式迁移 |
| 安全审查 | AI Security Review | OWASP Top 10 + 安全门禁的 AI 代码安全保障 |
| 反模式 | Anti-patterns | 8 大 AI 协作常见陷阱 + 真实失败案例 |
| 知识内化 | Knowledge Internalization | 将 AI 生成的知识转化为底层能力的过程 |

---

## 工具术语

| 术语 | 英文 | 定义 |
|------|------|------|
| AI 工具矩阵 | AI Tool Matrix | 模型、IDE、Agent 的对比选型框架 |
| MCP 服务器 | MCP Server | Model Context Protocol 服务器，提供工具和资源 |
| 上下文同步 | Context Sync | 自动维护项目 CONTEXT.md 的过程 |
| 架构决策记录 | ADR (Architecture Decision Record) | 记录关键架构决策的文档 |
| IDE 最佳实践 | IDE Best Practices | Zed/Cursor 配置与使用的最佳实践 |

---

## 学习术语

| 术语 | 英文 | 定义 |
|------|------|------|
| AI 学习法 | AI Learning Method | 用 LLM 快速攻克新领域的学习范式 |
| 知识内化 | Knowledge Internalization | 将 AI 生成的知识转化为底层能力的过程 |
| Prompt 工程 | Prompt Engineering | 编写高质量提示词的技术和方法 |

---

## 审计/质量术语 (来自 AUDIT_REPORT.md)

| 术语 | 英文 | 定义 |
|------|------|------|
| 任意文件写入 | Arbitrary File Write | 未验证路径即写入文件的安全漏洞 (SEC-01) |
| 路径遍历 | Path Traversal | 使用 `..` 逃出项目目录的攻击向量 |
| API 密钥泄露 | API Key Leakage | 密钥嵌入 URL 查询参数导致的暴露 (SEC-03) |
| 宽泛异常捕获 | Broad Exception Catch | 捕获 `Exception` 导致编程错误被吞没 (CODE-02) |
| 代码重复 | Code Duplication | 相同逻辑在多处出现 (CODE-03: 文件块解析 3 次) |
| 死代码 | Dead Code | 定义但未调用的方法 (CODE-04) |
| 脆弱 JSON 解析 | Fragile JSON Parsing | 用字符串查找提取 JSON，嵌套括号会失败 (CODE-09) |
| 断链 | Broken Link | 文档链接指向不存在的目标 (DOC-01: 18 个) |
| 测试覆盖不均 | Uneven Test Coverage | 模块间覆盖率差异大，7 模块 <50% (TEST-01) |

---

## 学习路径术语

| 术语 | 英文 | 定义 |
|------|------|------|
| 认知升级路径 | Mindset Upgrade Path | 理解"为什么"：product-thinking → solo-founder-loop → ai-to-market-checklist |
| 技能提升路径 | Skill Upgrade Path | 掌握"怎么做"：ai-learning-method → prompt-engineering → full-cycle-workflow |
| 工具赋能路径 | Tooling Path | 优化"用什么"：ai-tool-matrix → ide-best-practices → 实践案例 |
| 全面进化路径 | Comprehensive Path | 系统性提升：认知层 → 学习层 → 效率层 → 工具层 → 实践验证 |
| 前端专用路径 | Frontend-Focused Path | React/Vue/Next.js 开发者专用路径 |
| 后端专用路径 | Backend-Focused Path | API/微服务/数据库方向专用路径 |
| DevOps 专用路径 | DevOps-Focused Path | CI/CD/监控/基础设施自动化专用路径 |

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

## 术语使用规范

1. **中文优先**：文档优先使用中文术语，英文作为辅助参考
2. **统一大小写**：专有名词首字母大写，如 `MCP Server`、`ADR`、`OWASP`
3. **避免同义词**：如"质量门禁"统一使用，不使用"质量关卡"、"检查点"
4. **新增术语流程**：发现新术语 → 更新此表 → 同步相关文档 → 通知团队

---

*本表随新增术语时更新。最后更新: 2026-07-21*
