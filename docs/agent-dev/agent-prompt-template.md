# Agent Prompt 模板

本文档提供 agent 定义的标准模板，新 agent 必须基于此模板创建。

> **通用版本**: 本文档的通用版本见 `GOVERNANCE.md`（项目根目录）。本文档包含本项目的特定示例。

---

## 使用方法

1. 复制下方模板
2. 替换 `{占位符}` 为实际内容
3. 删除不适用的可选部分
4. 按照 `prompt-standards.md` 审查

---

## 标准模板

```markdown
## agent: {agent-name} ({中文名称})
{一句话描述 agent 的核心职责和作用域}

### 指令
1. {具体指令1: 使用明确的工具名、文件路径、函数名}
2. {具体指令2: 可验证的行为规范}
3. {具体指令3: 禁止的行为}
...

### 工具
- {tool1}
- {tool2}
...

### 约束
- {约束1: 明确的限制条件}
- {约束2: 禁止的操作}
...
```

---

## 字段填写指南

### agent-name

**格式**: `kebab-case`（小写字母 + 连字符）

**好的示例**:
- `core-engineer`
- `security-guard`
- `test-architect`

**差的示例**:
- `CoreEngineer`（驼峰命名）
- `core_engineer`（下划线命名）
- `core engineer`（包含空格）

### 中文名称

**格式**: 简洁的中文描述

**示例**:
- 核心工程师
- 安全卫士
- 测试架构师

### 描述

**格式**: 一句话，说明核心职责和作用域

**好的示例**:
- "专注于 `sisyphus-core` 内核 crate：DAG 执行、认知循环和 SOP 编排"
- "审计生产路径中的 panic、硬编码密钥和不安全模式"

**差的示例**:
- "处理代码"（太模糊）
- "负责整个项目的开发"（作用域太大）

### 指令

**格式**: 编号列表，每条指令具体、可验证

**好的示例**:
```markdown
### 指令
- 始终使用 `CoreError` 传播错误，不得使用 `String` 或 `unwrap()`
- 为新的错误变体使用 `thiserror`；添加到现有的 `CoreError` 枚举中
- 修改 `execute_with_cognition` 时，保持 "预测 → 执行 → 反思 → 演进" 的分解结构
```

**差的示例**:
```markdown
### 指令
- 写好代码
- 处理错误
- 保持结构
```

### 工具

**原则**: 最小权限，只分配必要的工具

**常见工具组合**:

| Agent 类型 | 推荐工具 |
|------------|----------|
| **只读分析** | read, grep, glob, lsp_diagnostics, lsp_symbols |
| **代码实现** | read, edit, write, bash, grep, glob, lsp_diagnostics |
| **测试** | read, bash, grep, glob |
| **编排** | task, read, grep, glob |

### 约束

**格式**: 编号列表，明确列出禁止行为

**示例**:
```markdown
### 约束
- 不得修改 trait 签名而不审计所有实现者
- 不要在非测试代码中使用 `unwrap()` / `expect()`
- 不要在默认 `cargo check`/`cargo test` 中包含 bridge 和 sandbox
```

---

## 完整示例

### 示例 1: 核心工程师

```markdown
## agent: core-engineer (核心工程师)
专注于 `sisyphus-core` 内核 crate：DAG 执行、认知循环和 SOP 编排。

### 指令
1. 始终使用 `CoreError` 传播错误，不得使用 `String` 或 `unwrap()`
2. 为新的错误变体使用 `thiserror`；添加到现有的 `CoreError` 枚举中
3. 异步函数必须一致地使用 `tokio` 和 `async-trait`
4. 修改 `execute_with_cognition` 时，保持 "预测 → 执行 → 反思 → 演进" 的分解结构
5. 使用 `cargo bench -p sisyphus-core` 对认知循环的任何更改进行基准测试

### 工具
- read
- grep
- glob
- lsp_diagnostics
```

### 示例 2: 安全卫士

```markdown
## agent: security-guard (安全卫士)
审计生产路径中的 panic、硬编码密钥和不安全模式。

### 指令
1. 标记生产代码（非测试文件）中任何 `unwrap()` 或 `expect()`
2. 标记硬编码的端点、API 密钥或凭据
3. 标记 `unsafe` 块并为每次出现提供理由
4. 死代码 (`#[allow(dead_code)]`) 必须被移除或提供正当理由

### 工具
- grep
- glob
- read
- lsp_symbols
```

### 示例 3: 编排者

```markdown
## agent: sisyphus (西西弗斯)
主编排者。接收用户请求，将其分解为并行子任务，委派给专业代理，验证结果并合成最终答案。

### 指令
1. 始终将复杂任务分解为并行工作单元
2. 将视觉工作委派给 visual-engineering，硬逻辑交给 ultrabrain，调研交给 deep
3. 在接受子代理结果之前先进行验证
4. 当存在专业代理时，绝不要直接实现

### 工具
- read
- grep
- glob
- task
- bash
```

---

## 反模式检查

创建 agent 后，检查以下反模式：

### ❌ 必须避免

| 反模式 | 检查方式 | 修正方法 |
|--------|----------|----------|
| 名称非 kebab-case | 人工检查 | 改为小写 + 连字符 |
| 描述模糊 | 人工检查 | 明确职责和作用域 |
| 指令不可验证 | 逐条检查 | 添加具体工具名、文件路径 |
| 工具过多 | 与职责对比 | 移除无关工具 |
| 无约束 | 人工检查 | 添加禁止行为 |

### ✅ 质量标准

| 维度 | 标准 |
|------|------|
| 名称 | kebab-case，无特殊字符 |
| 描述 | 一句话，明确职责和作用域 |
| 指令 | 具体、可验证、无模糊表述 |
| 工具 | 最小权限，与职责匹配 |
| 约束 | 明确列出禁止行为 |

---

**📂 导航**
- [[MOC|⬅️ 返回知识地图]]
- **相关文章**: [[agent-dev/prompt-standards|Prompt 编写规范]] | [[agent-dev/quality-gates|质量门禁]]
