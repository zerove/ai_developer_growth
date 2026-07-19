# AI Developer Growth: 知识地图

> 按认知维度组织的知识网络，帮助开发者在 AI 时代进化。

---

## 核心理念

当 AI 能写出 80% 的代码时，开发者的价值在于：
- **定义问题** → 模糊需求 → 精准指令
- **系统设计** → 构建可扩展的架构
- **快速迭代** → 原型 → 产品闭环

---

## 知识体系

### 🧠 认知层 (Mindset)
改变你与代码的关系。

| 主题 | 核心问题 | 关键洞察 | 文档 |
|------|----------|----------|------|
| 产品思维 | 从"如何实现"到"构建什么" | 摆脱实现陷阱，关注用户价值 | [[docs/mindset/product-thinking]] |
| 独立开发 | 一人公司如何运作 | 精益运作 + 认知资源管理 | [[docs/mindset/solo-founder-loop]] |
| 市场发布 | 从代码到产品的路径 | 0→1 路径 + 增长策略 | [[docs/mindset/ai-to-market-checklist]] |
| 团队采用 | 团队如何采用 AI？ | 企业案例 + 采用框架 | [[docs/mindset/team-adoption]] |
| 人机协作 | 如何与 AI 协作？ | 能力互补 + 信任校准 | [[docs/mindset/human-ai-collaboration]] |
| 团队度量 | 如何度量团队效能？ | 四维平衡计分卡 | [[docs/mindset/team-metrics]] |
| **能力模型** | **AI 时代开发者如何分级？** | **五维雷达图 + 成长路径** | **[[docs/mindset/capability-model]]** |

**推荐阅读顺序**: product-thinking → solo-founder-loop → ai-to-market-checklist → team-adoption → human-ai-collaboration → team-metrics

### 📚 学习层 (Learning)
掌握 AI 时代的学习范式。

| 主题 | 核心问题 | 关键洞察 | 文档 |
|------|----------|----------|------|
| AI 学习法 | 如何用 LLM 快速攻克新领域 | 好奇心→提示→实现→审视→内化 | [[docs/learning/ai-learning-method]] |
| 知识内化 | 避免 AI 依赖，构建底层能力 | 对抗能力错觉，构建底层能力 | [[docs/learning/knowledge-internalization]] |
| Prompt 工程 | 结构化提示词技巧 | CoT、Few-Shot、结构化输出 | [[docs/learning/prompt-engineering]] |

**推荐阅读顺序**: ai-learning-method → knowledge-internalization → prompt-engineering

### ⚡ 效率层 (Engineering)
将认知转化为生产力。

| 主题 | 核心问题 | 关键洞察 | 文档 |
|------|----------|----------|------|
| 全周期工作流 | 需求→设计→编码→测试→部署 | 意图→生成→验证→修正闭环 | [[docs/efficiency/full-cycle-workflow]] |
| 自动化修复 | Bug 的 AI 自动修复 | 感知→推理→行动→验证 | [[docs/efficiency/automated-bug-fixing]] |
| 反模式与失败案例 | 如何避免常见陷阱？ | 8 大反模式 + 真实案例 | [[docs/efficiency/anti-patterns]] |
| 上下文工程 | 如何精准传递上下文？ | 分层策略 + 验证方法论 | [[docs/efficiency/context-engineering]] |
| Token 成本控制 | 如何控制 AI 成本？ | 分层模型 + ROI 计算 | [[docs/efficiency/token-optimization]] |
| 多 Agent 编排 | 如何协作多个 Agent？ | 5 种编排模式 + 选择指南 | [[docs/efficiency/multi-agent-patterns]] |
| 度量体系 | 如何量化 AI 效果？ | 三维平衡计分卡 + 自动化采集 | [[docs/efficiency/metrics-framework]] |
| 迁移策略 | 如何引入 AI？ | 五阶段渐进式迁移 | [[docs/efficiency/legacy-ai-migration]] |
| 安全审查 | 如何保证 AI 代码安全？ | OWASP Top 10 + 安全门禁 | [[docs/efficiency/ai-security-review]] |
| 文档自动化 | 如何自动生成文档？ | API/注释/README 自动生成 | [[docs/efficiency/auto-documentation]] |
| 性能优化 | 如何优化 AI 代码？ | 数据库/内存/算法/缓存优化 | [[docs/efficiency/ai-code-performance]] |
| 开源协作 | 如何用 AI 参与开源？ | Issue/PR/文档 AI 协作 | [[docs/efficiency/oss-with-ai]] |
| 知识库使用 | 如何应用知识库？ | 文档引用规则 + 自动化配置 | [[docs/efficiency/knowledge-base-usage]] |
| CI/CD 工作流 | 如何自动化部署？ | GitHub Actions + 蓝绿部署 | [[docs/efficiency/ci-cd-workflow]] |
| 代码审查指南 | 如何审查 AI 代码？ | 审查清单 + 质量门禁 | [[docs/efficiency/code-review-guide]] |
| 调试工作流 | 如何 AI 辅助调试？ | 系统化调试 + 日志分析 | [[docs/efficiency/debugging-workflow]] |
| 错误处理模式 | 如何统一错误处理？ | 错误分类 + 恢复策略 | [[docs/efficiency/error-handling-patterns]] |
| API 设计指南 | 如何设计 API？ | RESTful 规范 + 响应格式 | [[docs/efficiency/api-design-guide]] |

**实战避坑**: full-cycle-workflow 包含了从 AI-Context-Sync 开发中提炼的 4 个避坑指南。anti-patterns.md 收集了真实失败案例。

### 🛠️ 工具层 (Tooling)
选择正确的工具组合。

| 主题 | 核心问题 | 关键洞察 | 文档 |
|------|----------|----------|------|
| 工具矩阵 | 模型/IDE/Agent 选型 | jcode vs opencode 深度对比 | [[docs/tools/ai-tool-matrix]] |
| IDE 实践 | Zed/Cursor 配置 | 极速编辑 + AI 协同 | [[docs/tools/ide-best-practices]] |

**最新更新**: 已更新至 Claude 4、GPT-5、jcode、opencode 等最新工具。

### 🤖 Agent 开发规范 (Agent Dev)
确保 agent 开发的质量和效率。

#### 通用治理标准 (适用于任何项目)

| 主题 | 核心问题 | 文档 |
|------|----------|------|
| 通用治理标准 | 项目开发的完整规范 | [[GOVERNANCE]] |
| 安装指南 | 如何在任何项目中使用 | [[docs/governance/INSTALL]] |

#### 编程语言规范

| 语言 | 核心问题 | 文档 |
|------|----------|------|
| Python | Python 项目特定规范 | [[docs/governance/languages/python]] |
| Rust | Rust 项目特定规范 | [[docs/governance/languages/rust]] |
| TypeScript | TS 项目特定规范 | [[docs/governance/languages/typescript]] |
| Go | Go 项目特定规范 | [[docs/governance/languages/go]] |
| Java | Java 项目特定规范 | [[docs/governance/languages/java]] |
| C# | C# 项目特定规范 | [[docs/governance/languages/csharp]] |
| Kotlin | Kotlin 项目特定规范 | [[docs/governance/languages/kotlin]] |
| PHP | PHP 项目特定规范 | [[docs/governance/languages/php]] |
| Ruby | Ruby 项目特定规范 | [[docs/governance/languages/ruby]] |
| C/C++ | C/C++ 项目特定规范 | [[docs/governance/languages/cpp]] |
| Swift | Swift 项目特定规范 | [[docs/governance/languages/swift]] |
| Scala | Scala 项目特定规范 | [[docs/governance/languages/scala]] |
| Elixir | Elixir 项目特定规范 | [[docs/governance/languages/elixir]] |

#### 框架规范

| 框架 | 核心问题 | 文档 |
|------|----------|------|
| React | React 项目特定规范 | [[docs/frameworks/react]] |
| Vue | Vue 项目特定规范 | [[docs/frameworks/vue]] |
| Angular | Angular 项目特定规范 | [[docs/frameworks/angular]] |
| Svelte | Svelte/SvelteKit 项目特定规范 | [[docs/frameworks/svelte]] |
| Next.js | Next.js 项目特定规范 | [[docs/frameworks/nextjs]] |
| NestJS | NestJS 项目特定规范 | [[docs/frameworks/nestjs]] |
| Express/Fastify | Express/Fastify 项目特定规范 | [[docs/frameworks/express]] |
| Flask | Flask 项目特定规范 | [[docs/frameworks/flask]] |
| Django | Django 项目特定规范 | [[docs/frameworks/django]] |
| FastAPI | FastAPI 项目特定规范 | [[docs/frameworks/fastapi]] |
| Spring Boot | Spring Boot 项目特定规范 | [[docs/frameworks/springboot]] |

#### DevOps 规范

| 主题 | 核心问题 | 文档 |
|------|----------|------|
| Docker | 容器化最佳实践 | [[docs/devops/docker]] |
| Kubernetes | K8s 部署与管理 | [[docs/devops/kubernetes]] |
| CI/CD | 持续集成/持续部署 | [[docs/devops/cicd]] |

#### 数据库规范

| 主题 | 核心问题 | 文档 |
|------|----------|------|
| SQL | 关系型数据库最佳实践 | [[docs/database/sql]] |
| NoSQL | 非关系型数据库最佳实践 | [[docs/database/nosql]] |

#### API 设计规范

| 主题 | 核心问题 | 文档 |
|------|----------|------|
| RESTful | REST API 设计 | [[docs/api/rest]] |
| GraphQL | GraphQL API 设计 | [[docs/api/graphql]] |
| gRPC | gRPC API 设计 | [[docs/api/grpc]] |

#### 安全规范

| 主题 | 核心问题 | 文档 |
|------|----------|------|
| 认证授权 | 认证模式与最佳实践 | [[docs/security/authentication]] |
| OWASP Top 10 | 安全风险防护 | [[docs/security/owasp]] |

#### 测试与工作流

| 主题 | 核心问题 | 文档 |
|------|----------|------|
| 测试策略 | 测试金字塔与最佳实践 | [[docs/testing/strategy]] |
| Git 工作流 | Git 分支与提交规范 | [[docs/testing/git-workflow]] |

#### 本项目特定规范

| 主题 | 核心问题 | 文档 |
|------|----------|------|
| Prompt 编写规范 | 如何编写高质量 agent 定义 | [[docs/agent-dev/prompt-standards]] |
| 开发流程规范 | agent 开发的全流程标准 | [[docs/agent-dev/workflow-standards]] |
| 质量门禁 | 各阶段的质量检查标准 | [[docs/agent-dev/quality-gates]] |
| 上下文管理 | 项目上下文的维护规范 | [[docs/agent-dev/context-management]] |
| Prompt 模板 | agent 定义的标准模板 | [[docs/agent-dev/agent-prompt-template]] |
| 质量检查清单 | 开发各阶段的检查项 | [[docs/agent-dev/quality-checklist]] |

---

## 实践验证

理论需要实践检验。以下是真实案例：

### 案例库 (11 个真实案例)

| 案例 | 场景 | 效率提升 | 核心洞察 |
|------|------|----------|----------|
| [[case-studies/ai-task-prioritizer\|任务优先级工具]] | CLI 工具开发 | 8x | TDD + AI = 极致效率 |
| [[case-studies/ai-context-sync-development\|AI-Context-Sync]] | 完整产品开发 | 12x | 结构化 Prompt 是关键 |
| [[case-studies/cli-tool-development\|CLI 工具开发]] | 命令行工具 | 4x | AI 加速样板代码生成 |
| [[case-studies/web-scraping-tool\|网页抓取工具]] | 数据采集 | 4x | 智能识别减少手动配置 |
| [[case-studies/data-pipeline\|数据处理管道]] | ETL 流程 | 4x | 插件化架构提高可扩展性 |
| [[case-studies/api-monitoring\|API 监控系统]] | 运维监控 | 4.5x | 配置驱动减少代码修改 |
| [[case-studies/database-migration\|数据库迁移]] | 数据库管理 | 4.4x | 自动化分析减少人工错误 |
| [[case-studies/legacy-refactoring\|遗留系统重构]] | 代码现代化 | 5x | 渐进式重构降低风险 |
| [[case-studies/production-debugging\|生产环境调试]] | 问题排查 | 6x | AI 辅助快速定位根因 |
| [[case-studies/api-design-implementation\|API 设计实现]] | 后端开发 | 5x | 契约先行保证接口质量 |
| [[case-studies/multi-agent-collaboration\|多 Agent 协作]] | 团队协作 | 5x | 角色专业化 + 工作流编排 |

### 代码示例
| 示例 | 核心机制 | 学习价值 |
|------|----------|----------|
| [[examples/self-correction-loop\|自我修正循环]] | AI 代码质量保证 | 验证→重试模式 |
| [[examples/multi-agent-orch\|多 Agent 协作]] | 模拟团队开发 | 角色分工 + 迭代 |

### 参考实现
| 项目 | 定位 | 价值 |
|------|------|------|
| [[examples/ai-context-sync/README\|AI-Context-Sync]] | 知识验证工具 | 方法论的实践检验 |

---

## 学习路径

### 路径 1: 认知升级
适合想理解"为什么"的开发者。
```
product-thinking → solo-founder-loop → ai-to-market-checklist
```

### 路径 2: 技能提升
适合想掌握"怎么做"的开发者。
```
ai-learning-method → prompt-engineering → full-cycle-workflow
```

### 路径 3: 工具赋能
适合想优化"用什么"的开发者。
```
ai-tool-matrix → ide-best-practices → 实践案例
```

### 路径 4: 全面进化
适合想系统性提升的开发者。
```
认知层 → 学习层 → 效率层 → 工具层 → 实践验证
```

### 路径 5: 前端专用 (Frontend-Focused)
适合 React/Vue/Next.js 开发者，聚焦 UI/UX 与组件化开发。

**核心组合**:
```
product-thinking → ai-learning-method → ide-best-practices → 实践案例
```

**推荐技术栈**:
- AI IDE: Cursor (React 优化) + Zed (极速补全)
- 模型: Claude 4 (复杂组件逻辑) + GPT-4o-mini (快速补全)
- 工具: v0.dev (UI 生成), CodeRabbit (PR 审查)

**实战重点**:
- 组件化 Prompt 设计
- 响应式布局 AI 辅助
- 状态管理模式选择
- 性能优化 (懒加载、代码分割)

### 路径 6: 后端专用 (Backend-Focused)
适合 API 开发、微服务、数据库优化方向的开发者。

**核心组合**:
```
ai-learning-method → knowledge-internalization → full-cycle-workflow → automated-bug-fixing
```

**推荐技术栈**:
- AI IDE: Zed (Rust 性能) + Claude Code (复杂推理)
- 模型: Claude 4 (架构设计) + Gemini 2.5 Pro (长上下文)
- 工具: Postbird (API 测试), AI-Context-Sync (上下文管理)

**实战重点**:
- API 契约设计
- 数据库 Schema 优化
- 微服务拆分策略
- 性能监控与调优

### 路径 7: DevOps 专用 (DevOps-Focused)
适合 CI/CD、监控、基础设施自动化方向的工程师。

**核心组合**:
```
ai-learning-method → automated-bug-fixing → full-cycle-workflow → ide-best-practices
```

**推荐技术栈**:
- AI IDE: Zed (Shell 集成) + Claude Code (脚本生成)
- 模型: Claude 4 (复杂脚本) + GPT-4o (快速补全)
- 工具: GitHub Actions (CI/CD), Terraform (IaC), Datadog (监控)

**实战重点**:
- CI/CD Pipeline 自动化
- 基础设施即代码 (IaC)
- 监控告警智能化
- 故障自动恢复

---

## 📊 知识覆盖率

| 维度 | 文档数 | 状态 |
|------|--------|------|
| 认知层 | 7 | ✅ 完整 |
| 学习层 | 3 | ✅ 完整 |
| 效率层 | 18 | ✅ 完整 |
| 工具层 | 2 | ✅ 完整 |
| 案例库 | 10 | ✅ 达标 |
| 代码示例 | 2 | ✅ 基础 |
| 学习路径 | 7 | ✅ 完整 |

---

## 治理框架工具

| 文件 | 用途 | 链接 |
|------|------|------|
| 可视化地图 | 整体架构图 | [[docs/governance/MAP]] |
| 快速参考卡 | 速查手册 | [[docs/governance/CHEATSHEET]] |
| 安装指南 | 快速入门 | [[docs/governance/INSTALL]] |

---

## 贡献

欢迎贡献案例、工具推荐、方法论改进。

详见 [[CONTRIBUTING|贡献指南]]。

---

*AI 时代的竞争是掌握 AI 的人与不掌握 AI 的人的竞争。*