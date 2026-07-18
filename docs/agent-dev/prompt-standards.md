# Agent Prompt 编写规范

本文档定义了 AI Agent 的 Prompt 编写标准，确保 agent 定义的一致性、可维护性和高质量。

> **通用版本**: 本文档的通用版本见 `GOVERNANCE.md`（项目根目录）。本文档包含本项目的特定示例和工具。

---

## 核心原则

### 1. 明确性 (Clarity)
每个 agent 必须有清晰的职责边界，避免职责重叠或模糊。

### 2. 结构化 (Structure)
使用统一的 Markdown 格式组织 agent 定义，便于机器解析和人类阅读。

### 3. 可测试性 (Testability)
agent 的行为必须可验证，包括工具调用结果和输出格式。

### 4. 最小权限 (Least Privilege)
每个 agent 只应访问其职责所需的工具，避免过度授权。

---

## Agent 定义格式

### 标准结构

```markdown
## agent: {agent-name} ({中文名称})
{一句话描述 agent 的核心职责}

### 指令
1. {具体指令1}
2. {具体指令2}
...

### 工具
- {tool1}
- {tool2}
...

### 约束
- {约束1}
- {约束2}
...
```

### 字段说明

| 字段 | 必填 | 说明 |
|------|------|------|
| `agent-name` | ✅ | 英文标识符，使用 kebab-case |
| `中文名称` | ✅ | 人类可读的名称 |
| `描述` | ✅ | 一句话说明 agent 的核心职责 |
| `指令` | ✅ | agent 必须遵守的具体规则 |
| `工具` | ✅ | agent 可使用的工具列表 |
| `约束` | ❌ | agent 的限制和禁止行为 |

---

## 指令编写规范

### 好的指令

```markdown
### 指令
- 始终使用 `CoreError` 传播错误，不得使用 `String` 或 `unwrap()`
- 为新的错误变体使用 `thiserror`；添加到现有的 `CoreError` 枚举中
- 修改 `execute_with_cognition` 时，保持 "预测 → 执行 → 反思 → 演进" 的分解结构
```

### 差的指令

```markdown
### 指令
- 写好代码
- 处理错误
- 保持结构
```

### 指令质量检查

| 维度 | 好的指令 | 差的指令 |
|------|----------|----------|
| **具体性** | "使用 `CoreError` 传播错误" | "处理错误" |
| **可验证性** | "测试覆盖率 > 80%" | "写测试" |
| **唯一性** | "只修改 `src/` 目录" | "修改代码" |
| **约束性** | "不得使用 `unwrap()`" | "注意 unwrap" |

---

## 工具分配规范

### 工具分类

| 类别 | 工具 | 适用 agent |
|------|------|-----------|
| **读取** | read, grep, glob | 所有 agent |
| **分析** | lsp_diagnostics, lsp_symbols | 代码质量 agent |
| **编辑** | edit, write | 实现 agent |
| **执行** | bash | 构建/测试 agent |
| **搜索** | lsp_find_references | 重构 agent |

### 分配原则

1. **只读 agent** (如 oracle): 只分配读取和分析工具
2. **实现 agent** (如 core-engineer): 分配完整工具集
3. **审查 agent** (如 security-guard): 分配读取和分析工具，不分配编辑工具

---

## Agent 类型定义

### 按职责分类

| 类型 | 职责 | 典型工具 |
|------|------|----------|
| **实现型** | 编写、修改代码 | read, edit, write, bash, grep |
| **分析型** | 审查、诊断代码 | read, grep, lsp_diagnostics |
| **搜索型** | 查找代码、文档 | read, grep, glob, websearch |
| **编排型** | 协调、委派任务 | task, read, grep |
| **规划型** | 设计、架构决策 | read, grep, glob |

### 按作用域分类

| 作用域 | 说明 | 示例 |
|--------|------|------|
| **模块级** | 负责单个模块 | core-engineer |
| **跨模块** | 负责多个模块的交互 | bridge-engineer |
| **全局** | 负责整个项目 | sisyphus |

---

## 错误处理规范

### Agent 错误类型

```markdown
### 错误处理
- 使用 `{ErrorType}` 传播所有错误
- 禁止使用 `unwrap()` / `expect()`（测试代码除外）
- 错误信息必须包含上下文（文件名、操作、原因）
```

### 错误传播模式

```rust
// 正确
fn do_something() -> Result<(), CoreError> {
    let config = load_config().map_err(|e| CoreError::Config(e))?;
    Ok(())
}

// 错误
fn do_something() {
    let config = unwrap(); // 禁止
}
```

---

## 测试规范

### Agent 测试要求

```markdown
### 测试
- 单元测试: 覆盖核心逻辑
- 集成测试: 验证模块交互
- 测试覆盖率: > 80%
```

### 测试结构

```markdown
### 测试
- 单元测试放 `src/` 下 `#[cfg(test)]`
- 集成测试放 `tests/`
- 基准测试用 `criterion`
```

---

## 示例：标准 Agent 定义

```markdown
## agent: core-engineer (核心工程师)
专注于 `sisyphus-core` 内核 crate：DAG 执行、认知循环和 SOP 编排。

### 指令
- 始终使用 `CoreError` 传播错误，不得使用 `String` 或 `unwrap()`
- 为新的错误变体使用 `thiserror`；添加到现有的 `CoreError` 枚举中
- 异步函数必须一致地使用 `tokio` 和 `async-trait`
- 修改 `execute_with_cognition` 时，保持 "预测 → 执行 → 反思 → 演进" 的分解结构
- 使用 `cargo bench -p sisyphus-core` 对认知循环的任何更改进行基准测试

### 工具
- read
- grep
- glob
- lsp_diagnostics
```

---

## 反模式

### ❌ 禁止的模式

1. **模糊指令**: "写好代码" → 应具体到工具、格式、约束
2. **过度授权**: 给只读 agent 分配编辑工具
3. **职责重叠**: 多个 agent 负责同一文件
4. **缺少约束**: 没有明确的禁止行为
5. **不可验证**: 指令无法通过测试验证

### ✅ 推荐的模式

1. **具体指令**: "使用 `thiserror` 定义错误" 
2. **最小权限**: 只分配必要的工具
3. **职责清晰**: 每个 agent 有明确的作用域
4. **约束明确**: 列出禁止的行为
5. **可验证**: 指令可以通过 LSP、测试验证

---

## 审查清单

在创建或修改 agent 时，检查以下项目：

- [ ] 名称清晰，符合 kebab-case
- [ ] 描述一句话说明核心职责
- [ ] 指令具体、可验证
- [ ] 工具列表符合最小权限原则
- [ ] 没有职责重叠的 agent
- [ ] 错误处理规范明确
- [ ] 测试要求明确

---

**📂 导航**
- [[MOC|⬅️ 返回知识地图]]
- **相关文章**: [[agent-dev/workflow-standards|开发流程规范]] | [[agent-dev/quality-gates|质量门禁]]
