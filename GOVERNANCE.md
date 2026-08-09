# Universal Agent Development Governance

> 通用的 AI Agent 开发治理标准，适用于任何项目。

---

## 1. Agent 定义格式

所有 agent 定义必须包含以下字段：

```yaml
agent-name: kebab-case 命名 (如: code-reviewer)
描述: 一句话核心职责
工具: 最小权限列表
约束: 明确的禁止行为
指令: 具体、可验证的操作步骤
```

### 命名规范

- 使用 kebab-case: `code-reviewer`, `test-runner`
- 名词+动词或动词+名词: `bug-fixer`, `deploy-helper`
- 避免缩写: 用 `helper` 不用 `hlp`

### 指令编写原则

1. **具体性**: 每条指令必须包含具体的工具名、文件路径、函数名
2. **可验证性**: 指令执行后必须有明确的成功/失败判定
3. **原子性**: 一条指令只做一件事
4. **顺序性**: 指令必须按逻辑顺序排列

---

## 2. 开发流程 (5 步闭环)

```
需求分析 → Prompt 设计 → 实现编码 → 自动化审计 → 资产更新
   ①          ②          ③          ④           ⑤
```

### 阶段详情

| 阶段 | 输入 | 输出 | 负责人 |
|------|------|------|--------|
| ① 需求分析 | 用户需求 | 需求文档 | PM/TL |
| ② Prompt 设计 | 需求文档 | Agent 定义 | Agent Dev |
| ③ 实现编码 | Agent 定义 | 可执行代码 | Agent Dev |
| ④ 自动化审计 | 可执行代码 | 审计报告 | CI/CD |
| ⑤ 资产更新 | 审计报告 | 更新文档 | Agent Dev |

### 不可跳过的阶段

- ① 需求分析: 必须明确职责边界，与现有 agent 无重叠
- ④ 自动化审计: 必须通过质量检查才能合并

---

## 3. 质量门禁 (4 道门禁)

### Gate 1: Prompt 设计审查

**检查项**:
- [ ] Agent 名称符合命名规范
- [ ] 描述清晰、无歧义
- [ ] 指令具体、可验证
- [ ] 工具权限最小化
- [ ] 约束明确、无遗漏

**执行方式**: 人工审查

### Gate 2: 实现编码审查

**检查项**:
- [ ] 代码符合项目编码规范
- [ ] 无 `unwrap()`/`expect()` 在生产代码
- [ ] 无 `as any`/`@ts-ignore` 类型抑制
- [ ] 错误处理完整
- [ ] 测试覆盖核心逻辑

**执行方式**: Linter + 类型检查 + 人工审查

### Gate 3: 自动化审计

**检查项**:
- [ ] Agent 定义格式正确
- [ ] 工具权限符合最小权限原则
- [ ] 无硬编码路径或密钥
- [ ] 依赖项安全扫描通过

**执行方式**: CI/CD 自动执行

### Gate 4: 资产更新审查

**检查项**:
- [ ] README.md 已更新 (如有新 agent)
- [ ] INDEX.md 已更新 (如有新文档)
- [ ] CONTEXT.md 已更新 (如有状态变化)
- [ ] ADR.md 已更新 (如有架构决策)

**执行方式**: 人工审查

---

## 4. 上下文管理

### 必须维护的文件

| 文件 | 用途 | 更新频率 |
|------|------|----------|
| `CONTEXT.md` | 项目状态、当前焦点、阻塞项 | 每次重大迭代后 |
| `ADR.md` | 架构决策记录 | 关键决策时 |
| `AGENTS.md` | Agent 定义汇总 | 新增/修改 agent 时 |
| `UBIQUITOUS_LANGUAGE.md` | 领域术语表 | 新增术语时 |

### 更新原则

1. **及时性**: 状态变化后 24 小时内更新
2. **准确性**: 只记录事实，不记录推测
3. **简洁性**: 用 bullet points，避免长段落
4. **可追溯性**: 重大决策必须记录原因

---

## 5. 代码规范

### 通用标准

| 维度 | 标准 |
|------|------|
| 错误处理 | 使用自定义 Error 类型，禁止 `unwrap()`/`expect()` |
| 类型安全 | 禁止 `as any` / `@ts-ignore` / `@ts-expect-error` |
| 文件大小 | 单文件不超过 300 行 |
| 函数大小 | 单函数不超过 50 行 |
| 测试覆盖 | 核心逻辑 > 80% |

### 提交规范

```
<type>(<scope>): <description>

feat(agent): add code-reviewer agent
fix(doc): correct link in README
refactor(tools): extract common utilities
```

---

## 6. 多 Agent 协作

### 协作模式

| 场景 | 推荐模式 | 说明 |
|------|----------|------|
| Bug 修复 | 串行流水线 | 定位→修复→验证 |
| 新功能开发 | 并行扇出 | 设计→实现→测试 |
| 代码重构 | 主从模式 | 主 agent 协调，子 agent 执行 |
| 架构设计 | 对等协作 | 多 agent 讨论，达成共识 |

### 通信协议

1. **请求**: 明确说明需求、上下文、期望输出
2. **响应**: 提供结果、状态、下一步建议
3. **冲突**: 升级到人工决策，不要自行假设

---

## 7. 安全规范

### 禁止行为

- ❌ 硬编码密钥、密码、token
- ❌ 提交敏感信息到版本控制
- ❌ 无授权访问外部服务
- ❌ 执行高风险操作 (删除数据、重置系统)

### 必须行为

- ✅ 使用环境变量或密钥管理服务
- ✅ 最小权限原则
- ✅ 输入验证和输出编码
- ✅ 日志脱敏

---

## 8. 文档规范

### 文档类型

| 类型 | 路径 | 用途 |
|------|------|------|
| 方法论文档 | `docs/{category}/{name}.md` | 知识沉淀 |
| 案例研究 | `case-studies/{name}.md` | 实践验证 |
| Agent 定义 | `agents/{name}.md` | Agent 配置 |
| 决策记录 | `docs/adr/{id}-{title}.md` | 架构决策 |

### 文档结构

每个文档必须包含：
1. **标题**: 清晰、描述性
2. **概述**: 一句话说明文档目的
3. **正文**: 结构化内容
4. **导航**: 底部 `📂 导航` 部分
5. **更新记录**: 最后更新时间

---

## 9. 安装指南

### 在你的项目中使用

1. **复制标准文件**:
   ```bash
   cp GOVERNANCE.md /path/to/your/project/
   ```

2. **选择语言特定规则** (可选):
   ```bash
   mkdir -p docs/governance/languages
   cp docs/governance/languages/{python,rust,typescript,go}.md /path/to/your/project/docs/governance/languages/
   ```

3. **配置 CI/CD** (可选):
   - 添加质量门禁检查
   - 配置自动化审计

4. **团队培训**:
   - 阅读本文档
   - 理解质量门禁
   - 遵守开发流程

---

## 10. 语言、框架和领域规范

详见 `docs/governance/languages/`、`docs/frameworks/` 和 `docs/` 目录：

### 编程语言 (18 种)

- [Python](docs/governance/languages/python.md)
- [JavaScript](docs/governance/languages/javascript.md)
- [TypeScript](docs/governance/languages/typescript.md)
- [Rust](docs/governance/languages/rust.md)
- [Go](docs/governance/languages/go.md)
- [Java](docs/governance/languages/java.md)
- [C#](docs/governance/languages/csharp.md)
- [Kotlin](docs/governance/languages/kotlin.md)
- [PHP](docs/governance/languages/php.md)
- [Ruby](docs/governance/languages/ruby.md)
- [C/C++](docs/governance/languages/cpp.md)
- [Swift](docs/governance/languages/swift.md)
- [Scala](docs/governance/languages/scala.md)
- [Elixir](docs/governance/languages/elixir.md)
- [Dart](docs/governance/languages/dart.md)
- [R](docs/governance/languages/r.md)
- [SQL](docs/governance/languages/sql.md)
- [Shell/Bash](docs/governance/languages/shell.md)

### 框架 (11 种)

- [React](docs/frameworks/react.md)
- [Vue](docs/frameworks/vue.md)
- [Angular](docs/frameworks/angular.md)
- [Svelte](docs/frameworks/svelte.md)
- [Next.js](docs/frameworks/nextjs.md)
- [NestJS](docs/frameworks/nestjs.md)
- [Express/Fastify](docs/frameworks/express.md)
- [Flask](docs/frameworks/flask.md)
- [Django](docs/frameworks/django.md)
- [FastAPI](docs/frameworks/fastapi.md)
- [Spring Boot](docs/frameworks/springboot.md)

### 领域规范

- [Docker](docs/devops/docker.md)
- [Kubernetes](docs/devops/kubernetes.md)
- [CI/CD](docs/devops/cicd.md)
- [SQL](docs/database/sql.md)
- [NoSQL](docs/database/nosql.md)
- [RESTful API](docs/api/rest.md)
- [GraphQL](docs/api/graphql.md)
- [gRPC](docs/api/grpc.md)
- [认证授权](docs/security/authentication.md)
- [OWASP Top 10](docs/security/owasp.md)
- [测试策略](docs/testing/strategy.md)
- [Git 工作流](docs/testing/git-workflow.md)

---

## 11. AI 开发流程规范 (15 个标准文档)

AI 辅助开发需要额外的流程规范。以下15个标准文档覆盖了从代码生成到部署运维的完整链路。

### 治理层 (P0 - 核心流程)

| 标准 | 描述 | 关键内容 |
|------|------|----------|
| [AI 代码生成质量标准](docs/efficiency/ai-code-generation-quality.md) | 幻觉检测、输出验证、代码标注 | 三级验证体系、幻觉分类、持续改进 |
| [AI 模型选型与评估标准](docs/efficiency/ai-model-selection.md) | 选型、多模型协作 | 决策树、评估框架、月度审查 |
| [AI 开发全生命周期标准](docs/efficiency/ai-sdlc.md) | 7 阶段 SDLC、质量门禁、度量指标 | 需求→设计→实现→测试→部署→监控→维护 |
| [AI 代码审查专项清单](docs/efficiency/ai-code-review-checklist.md) | 幻觉检测、模式复制、过度简化 | H/P/S/C 四类检查项 |
| [AI 非确定性输出测试标准](docs/efficiency/ai-nondeterministic-testing.md) | 属性测试、模糊测试、契约测试 | 四层测试金字塔 |

### 治理层 (P1 - 工程实践)

| 标准 | 描述 | 关键内容 |
|------|------|----------|
| [AI 幻觉检测与缓解标准](docs/efficiency/ai-hallucination-mitigation.md) | 幻觉分类、检测方法、缓解策略 | L1-L4 严重等级、三级检测 |
| [AI 代码归属与许可证标准](docs/efficiency/ai-code-licensing.md) | 版权归属、许可证合规、法律风险 | 归属标注、许可证兼容矩阵 |
| [AI 开发环境配置标准](docs/efficiency/ai-dev-environment.md) | IDE 配置、工具链、Git Hooks | 推荐配置、团队共享 |
| [AI 上下文窗口管理标准](docs/efficiency/ai-context-window-management.md) | 分层上下文、成本优化、会话管理 | 三层模型、预算分配 |
| [AI 开发性能基准标准](docs/efficiency/ai-performance-benchmarks.md) | 效率指标、基准测试、度量体系 | 效率/质量/成本三维指标 |

### 效率层 (P2 - 补充完善)

| 标准 | 描述 | 关键内容 |
|------|------|----------|
| [AI 调试专项标准](docs/efficiency/ai-debugging-standards.md) | 调试工作流和方法论 | 5步调试流程、Prompt模板 |
| [AI 代码版本控制标准](docs/efficiency/ai-version-control.md) | 版本管理、分支策略、回滚机制 | 提交规范、分支模型 |
| [AI 部署与运维标准](docs/efficiency/ai-deployment-operations.md) | 部署检查清单、监控告警 | 蓝绿部署、金丝雀发布 |
| [AI 开发者培训标准](docs/efficiency/ai-developer-training.md) | 能力模型、培训路径、认证体系 | L1-L5 能力等级 |
| [AI 开发工具链标准](docs/efficiency/ai-dev-toolchain.md) | 工具选型、配置标准、评估方法 | 工具矩阵、选型决策 |

---

---

## 附录: 质量检查清单

### Agent 定义检查

- [ ] 名称符合 kebab-case 规范
- [ ] 描述清晰、无歧义
- [ ] 指令具体、可验证
- [ ] 工具权限最小化
- [ ] 约束明确、无遗漏
- [ ] 无与现有 agent 重叠

### 代码检查

- [ ] 无 `unwrap()`/`expect()` 在生产代码
- [ ] 无 `as any`/`@ts-ignore` 类型抑制
- [ ] 错误处理完整
- [ ] 测试覆盖核心逻辑
- [ ] 符合项目编码规范

### 文档检查

  -   [ ] README.md 已更新
  -   [ ] INDEX.md 已更新
  -   [ ] CONTEXT.md 已更新
  -   [ ] ADR.md 已更新 (如有架构决策)

---

_本标准随项目演进持续更新。最后更新: 2026-07-23_
