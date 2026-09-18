---
title: "无限语言支持架构"
description: "jcode + LLM 可以开发几乎所有编程语言。aidevelopergrowth 如..."
category: 工具层
tags: ['无限语言支持架构', '可以开发几乎所有编程语言', '如何支持', '三层质量保障', '能生成的任何语言', '通用规则层']
difficulty: 基础
---

# 无限语言支持架构

jcode + LLM 可以开发几乎所有编程语言。ai_developer_growth 如何支持？

## 三层质量保障

```
                    LLM 能生成的任何语言
                            │
                ┌───────────┼───────────┐
                ▼           ▼           ▼
         ┌──────────┐ ┌──────────┐ ┌──────────┐
         │ 通用规则层 │ │ 语言规则层 │ │ LLM 生成层 │
         │ (universal)│ │ (26语言)  │ │ (动态)    │
         └──────────┘ └──────────┘ └──────────┘
```

### 第一层: 通用规则 (universal.yml) — 跨语言

适用于**所有**编程语言。不依赖任何特定语法。

| 规则 | 覆盖语言 | 检测内容 |
|------|----------|----------|
| 硬编码密钥 | ALL | password/secrets/token 赋值 |
| 命令注入 | ALL | shell 字符串拼接 |
| SQL 注入 | ALL | 查询字符串拼接 |
| 空异常处理 | ALL | empty catch/except/rescue |
| 忽略错误 | ALL | `_ = err` 模式 |
| 调试输出 | ALL | print/console.log/puts |
| 硬编码地址 | ALL | localhost 硬编码 |
| 深层嵌套 | ALL | if 嵌套超过阈值 |
| TODO/FIXME | ALL | 未完成标记 |
| 注释代码 | ALL | 注释掉的代码行 |
| 未验证输入 | ALL | read/gets/input 无验证 |
| 未关闭资源 | ALL | open 无 close/with/defer |

### 第二层: 语言规则 (26 languages) — 已优化

当前 26 种语言，每种 22-42 条专用规则，覆盖 9 个质量维度。

### 第三层: LLM 动态生成 — 无限扩展

对于未支持的任意语言 (Mojo, Gleam, Roc, Odin 等):

1. `/governance check` 检测到文件类型无匹配规则
2. 规则引擎自动加载 `universal.yml`（15+ 条规则立即生效）
3. jcode 调用 LLM 生成该语言特定的补充规则
4. 规则缓存到 `~/.jcode/governance/languages/` 目录
5. 下次相同语言自动使用缓存的规则

### 多语言支持分级策略 (Language Support Tiers)

为了平衡多语言覆盖广度与深度，项目将语言支持划分为三个明确的治理等级：

- **Tier 1 (深度支持)**：Python, TypeScript / JavaScript
  - **能力**：完整 AST 符号解析、类型检查（Mypy/TS）、死代码/未引用导入检测、复杂度指标计算、专用 AST 规则及外部 Linter (Ruff/ESLint/Bandit) 深度集成。
- **Tier 2 (标准支持)**：Go, Rust, Java, C#, C++, PHP, Ruby, Kotlin, Swift 等 24+ 语言
  - **能力**：规则引擎静态 YAML 规则匹配、命名规范检查、反模式扫描，以及原生 Linter (Clippy/Golangci-lint 等) 聚合。
- **Tier 3 (动态扩展支持)**：其他任意新兴语言 (Mojo, Gleam, Roc 等)
  - **能力**：通用规则层 (`universal.yml`) 兜底 + LLM 动态规则生成与缓存。

## 开发者体验

```bash
# 编写 Mojo 代码（ai-dev-framework 不支持）
cat > hello.mojo << 'EOF'
fn main():
    var password = "hunter2"
    print(password)
EOF

# jcode 自动检查
/governance check hello.mojo
# ✅ 通用规则生效:
#   - 硬编码密钥检测 (error)
#   - print 调试输出 (info)
# 💡 LLM 生成 Mojo 专用规则...
# ✅ 发现 2 个 Mojo 特定问题:
#   - mo-unsafe-ptr: Unsafe block found
#   - mo-var-overuse: Consider 'let' instead of 'var'
```

## 完整工作流

```
jcode 打开 .mojo 文件
  │
  ├── 检测语言: Mojo
  │
  ├── ai-dev-framework 有 Mojo 规则吗?
  │   ├── 有 → 加载 26+ 条专用规则
  │   └── 无 → 加载 universal.yml (15 条)
  │               │
  │               └── LLM 生成 Mojo 补充规则 (5-8 条)
  │                     │
  │                     └── 缓存到 ~/.jcode/governance/languages/mojo/...
  │
  └── 执行全部质量检查: 通用 + 语言 + LLM 生成
```

## 优势

| 方案 | 支持语言数 | 维护成本 | 质量 |
|------|-----------|---------|------|
| 纯静态 YAML | 26 | 高 | 高 |
| 纯 LLM 规则 | 无限 | 零 | 中 |
| **三层混合** | **无限** | **低** | **高** |

## 当前状态

| 层 | 状态 | 语言数 |
|----|------|--------|
| 通用规则 (universal.yml) | ✅ 已实现 | ALL |
| 规则引擎加载 | ✅ 已改造 | 26 + ALL |
| LLM Prompt 模板 | ✅ 已设计 | 文档就绪 |
| LLM 生成集成 | 📋 待 jcode 平台集成 | 下一步 |
