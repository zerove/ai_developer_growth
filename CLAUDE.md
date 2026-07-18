# AI Developer Growth: Agent 开发治理规范

> 本文件是所有 AI Agent 的系统指令。任何在此项目中工作的 agent 必须遵守以下规范。

---

## 通用治理标准

本项目遵循 `GOVERNANCE.md` 中的通用治理标准。该标准适用于任何项目，包含：
- Agent 定义格式
- 5 步开发流程
- 4 道质量门禁
- 上下文管理规范

**在你的项目中使用**: 复制 `GOVERNANCE.md` 到项目根目录即可。

---

## 项目定位

开源知识库，帮助开发者在 AI 时代实现指数级成长。核心产品是**知识文档**和**实践案例**，而非代码工具。

---

## Agent 开发规范 (强制)

所有 agent 定义、修改、评审必须遵守 `docs/agent-dev/` 下的规范：

### 1. Agent 定义格式

新 agent 必须使用 `docs/agent-dev/agent-prompt-template.md` 模板，包含：
- `agent-name`: kebab-case 命名
- `描述`: 一句话核心职责
- `指令`: 每条指令具体、可验证（包含工具名、文件路径、函数名）
- `工具`: 最小权限原则
- `约束`: 明确的禁止行为

详细标准见 `docs/agent-dev/prompt-standards.md`。

### 2. 开发流程

按 `docs/agent-dev/workflow-standards.md` 的 5 步闭环执行：

```
需求分析 → Prompt 设计 → 实现编码 → 自动化审计 → 资产更新
   ①          ②          ③          ④           ⑤
```

**不可跳过的阶段**：
- ① 需求分析：明确职责边界，与现有 agent 无重叠
- ④ 自动化审计：`ai_guard` + `ai_audit` 必须通过

### 3. 质量门禁

按 `docs/agent-dev/quality-gates.md` 的 4 道门禁执行：

| Gate | 检查内容 | 执行方式 |
|------|----------|----------|
| Gate 1 | Prompt 设计审查 | 人工/对照模板 |
| Gate 2 | 实现编码审查 | grep + LSP |
| Gate 3 | 自动化审计 | ai_guard + ai_audit + 测试 |
| Gate 4 | 资产更新审查 | 人工检查文档一致性 |

**不可豁免项**：
- 生产代码使用 `unwrap()`/`expect()`
- LSP 有 error 级别问题
- 测试失败
- `ai_guard`/`ai_audit` 有违规项

### 4. 上下文管理

按 `docs/agent-dev/context-management.md` 维护项目上下文：
- `CONTEXT.md`: 项目状态（每次重大迭代后更新）
- `ADR.md`: 架构决策记录（关键决策时更新）
- `AGENTS.md`: Agent 定义（新增/修改 agent 时更新）
- `UBIQUITOUS_LANGUAGE.md`: 领域术语表（新增术语时更新）

---

## 代码规范

### 通用标准

| 维度 | 标准 |
|------|------|
| 错误处理 | 使用自定义 Error 类型，禁止 `unwrap()`/`expect()` |
| 类型安全 | 禁止 `as any` / `@ts-ignore` / `@ts-expect-error` |
| 文件大小 | 单文件不超过 300 行 |
| 函数大小 | 单函数不超过 50 行 |
| 测试覆盖 | 核心逻辑 > 80% |

### Python 项目

- 使用 `ruff` 格式化和 lint
- 类型注解完整
- 使用 `thiserror` 或自定义异常

### 提交规范

```
<type>(<scope>): <description>

feat(agent): add core-engineer agent definition
fix(doc): correct link in README
refactor(tools): extract common utilities
docs(case-study): add new case study
```

---

## 多 Agent 协作

当多个 agent 协作时，参考 `docs/efficiency/multi-agent-patterns.md` 选择编排模式：

| 场景 | 推荐模式 |
|------|----------|
| Bug 修复 | 串行流水线 |
| 新功能开发 | 并行扇出 |
| 代码重构 | 主从模式 |
| 架构设计 | 对等协作 |

---

## 文档规范

### 案例研究

路径: `case-studies/{name}.md`

必须包含：背景、AI 协作过程、效率对比数据、关键洞察。

### 方法论文档

路径: `docs/{category}/{name}.md`

必须包含：导航链接（底部 `📂 导航`）、与 INDEX.md 的交叉引用。

### 贡献指南

详见 `CONTRIBUTING.md`。

---

## 工具使用

### 必须使用

- `ai_sync` / `ai_guard` / `ai_audit`: 上下文同步和质量审计
- `lsp_diagnostics`: 代码质量检查
- `grep` / `glob`: 模式搜索

### 禁止使用

- 不得在生产代码中使用 `unwrap()` / `expect()`
- 不得跳过质量门禁直接提交
- 不得在未更新文档的情况下完成开发

---

*本文件随项目演进持续更新。最后更新: 2026-07-17*
