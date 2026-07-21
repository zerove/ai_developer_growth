---
title: Agent 开发质量检查清单
description: 本文档提供 agent 开发各阶段的质量检查清单，确保交付物满足质量要求。
category: 治理层
tags: ['测试', 'checklist', 'AI', 'quality']
difficulty: 初级
reading_time: 10 分钟
updated: 2026-07-21
---

# Agent 开发质量检查清单

本文档提供 agent 开发各阶段的质量检查清单，确保交付物满足质量要求。

> **通用版本**: 本文档的通用版本见 `GOVERNANCE.md`（项目根目录）。本文档包含本项目的特定检查项。

---

## 使用方法

1. 在对应阶段完成检查项
2. 在 `[ ]` 中标记 `[x]` 表示通过
3. 未通过项必须修复后重新检查
4. Gate 审查时核对此清单

---

## Gate 1: Prompt 设计检查

### 基本信息

- [ ] **名称格式**: kebab-case，无特殊字符
- [ ] **中文名称**: 简洁明了
- [ ] **描述完整**: 一句话说明核心职责和作用域

### 指令质量

- [ ] **具体性**: 每条指令包含具体工具名、文件路径或函数名
- [ ] **可验证性**: 每条指令可通过 LSP、grep 或测试验证
- [ ] **唯一性**: 无重复或矛盾的指令
- [ ] **完整性**: 覆盖错误处理、异步规范、测试要求等

### 工具分配

- [ ] **最小权限**: 只分配必要的工具
- [ ] **无冗余**: 移除与职责无关的工具
- [ ] **分类正确**: 只读 agent 不分配编辑工具

### 职责边界

- [ ] **无重叠**: 与现有 agent 职责无冲突
- [ ] **作用域明确**: 明确负责的文件/模块范围
- [ ] **约束完整**: 列出禁止行为

---

## Gate 2: 实现编码检查

### 代码质量

- [ ] **无 `unwrap()`**: `grep -rn "unwrap()" src/` 返回空
- [ ] **无 `expect()`**: `grep -rn "expect()" src/` 返回空
- [ ] **错误类型**: 使用 `thiserror` 定义自定义 Error
- [ ] **异步规范**: 使用 `tokio` + `async-trait`
- [ ] **类型安全**: LSP 无 error 级别警告

### 文件规范

- [ ] **文件大小**: 单文件 < 300 行
- [ ] **函数大小**: 单函数 < 50 行
- [ ] **命名规范**: 符合语言惯例（snake_case / kebab-case）

### 提交规范

- [ ] **提交粒度**: 一个功能点一个 commit
- [ ] **提交信息**: 符合 Conventional Commits 格式
- [ ] **无敏感信息**: 无密钥、密码、token

---

## Gate 3: 自动化审计检查

### AI-Context-Sync 审计

- [ ] **上下文同步**: `ai_sync` 执行成功
- [ ] **架构合规**: `ai_guard` 无违规项
- [ ] **规范合规**: `ai_audit` 无违规项

### LSP 审计

- [ ] **语法正确**: `cargo check` 0 errors
- [ ] **类型正确**: LSP diagnostics 0 errors
- [ ] **无警告**: LSP diagnostics 0 warnings（可选）

### 测试审计

- [ ] **单元测试**: `cargo test` 全部通过
- [ ] **集成测试**: `cargo test --workspace` 全部通过
- [ ] **测试覆盖**: 核心逻辑 > 80%

---

## Gate 4: 资产更新检查

### 文档完整性

- [ ] **CONTEXT.md**: 包含新增 agent 信息
- [ ] **ADR.md**: 关键决策已记录（如适用）
- [ ] **AGENTS.md**: agent 定义已添加
- [ ] **UBIQUITOUS_LANGUAGE.md**: 新术语已定义（如适用）

### 一致性

- [ ] **代码与文档一致**: 描述与实现匹配
- [ ] **术语一致**: 与 UBIQUITOUS_LANGUAGE.md 一致

---

## MCP 工具检查（如适用）

### 工具定义

- [ ] **注册方式**: 使用 `@mcp.tool()` 装饰器
- [ ] **类型注解**: 参数有完整的类型提示
- [ ] **文档字符串**: docstring 详细描述工具功能
- [ ] **返回类型**: 返回 `str`（JSON 格式）

### 错误处理

- [ ] **异常捕获**: 使用 `try...except` 包裹
- [ ] **错误响应**: 返回 `{"status": "error", "message": "..."}` 格式
- [ ] **不抛异常**: 不向 MCP 宿主抛出异常

### 响应格式

- [ ] **成功响应**: `{"status": "success", "data": {...}}`
- [ ] **错误响应**: `{"status": "error", "message": "..."}`
- [ ] **JSON 编码**: 使用 `json.dumps()` 序列化

---

## 快速检查命令

### Gate 1（人工）

```bash
# 检查 agent 定义是否符合模板
cat AGENTS.md | grep -A 20 "## agent:"
```

### Gate 2

```bash
# 检查 unwrap/expect
grep -rn "unwrap()\|expect()" src/

# 检查文件大小
find src/ -name "*.rs" -exec wc -l {} \; | sort -rn

# LSP 检查
cargo check
```

### Gate 3

```bash
# AI-Context-Sync 审计
ai_sync
ai_guard
ai_audit

# 测试
cargo test
cargo test --workspace
```

### Gate 4（人工）

```bash
# 检查文档更新
cat CONTEXT.md
cat ADR.md
cat AGENTS.md
```

---

## 例外处理

### 可豁免（需说明理由）

| 情况 | 豁免条件 |
|------|----------|
| 测试覆盖率略低 | 核心逻辑 > 80%，工具函数可降低 |
| 文件略超 300 行 | 有合理原因（如自动生成） |
| 部分文档未更新 | 非关键文档，需在下次迭代补充 |

### 不可豁免

- ❌ 生产代码使用 `unwrap()`/`expect()`
- ❌ LSP 有 error 级别问题
- ❌ 测试失败
- ❌ `ai_guard`/`ai_audit` 有违规项

---

## 签名

完成所有检查后，签名确认：

```
Agent: {agent-name}
版本: {version}
检查人: {name}
日期: {date}
Gate 1: [通过/不通过]
Gate 2: [通过/不通过]
Gate 3: [通过/不通过]
Gate 4: [通过/不通过]
最终结果: [通过/不通过]
```

---

**📂 导航**
- [[MOC|⬅️ 返回知识地图]]
- **相关文章**: [[agent-dev/quality-gates|质量门禁标准]] | [[agent-dev/prompt-standards|Prompt 编写规范]]
