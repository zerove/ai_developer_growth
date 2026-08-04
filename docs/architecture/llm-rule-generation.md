---
title: "LLM-Guided Language Rule Generation"
description: "当 jcode 遇到 ai-dev-framework 不支持的编程语言时，通过此方法动..."
category: 工具层
tags: ['遇到', '不支持的编程语言时', '通过此方法动态生成规则', '触发条件', '用户编写', '等语言代码']
difficulty: 基础
---

# LLM-Guided Language Rule Generation

当 jcode 遇到 ai-dev-framework 不支持的编程语言时，通过此方法动态生成规则。

## 触发条件

1. 用户编写 Mojo、Gleam、Roc、Zig 等语言代码
2. `/governance check` 检测到未知语言
3. 规则引擎加载 `common/universal.yml`（15+ 通用规则）作为基线
4. jcode 自动调用 LLM 生成语言特定的补充规则

## LLM Prompt 模板

```markdown
你是一个代码质量专家。请为 {语言名称} 生成一组代码检查规则。

要求:
1. 输出 YAML 格式，与 ai-dev-framework 兼容
2. 包含该语言最常见的 5-8 个反模式
3. 每个反模式包含: id, name, severity, category, pattern(regex), message, fix_hint
4. 类别从以下选择: security, error_handling, performance, code_quality, type_safety, memory_safety, concurrency

语言信息:
- 名称: {语言名称}
- 类型: {静态/动态/脚本/系统}
- 核心特性: {特性描述}
- 常见陷阱: {已知陷阱}

规则文件路径: ai-dev-framework/languages/{语言名称}/rules.d/anti_patterns.yml
命名规范规则: ai-dev-framework/languages/{语言名称}/rules.d/anti_patterns.yml 中的 naming: 字段
阈值配置: thresholds: { max_function_length: 50, max_file_length: 500 }

请只返回有效的 YAML 内容。
```

## 示例: Mojo 语言

当检测到 `.mojo` 文件且无规则文件时:

```yaml
anti_patterns:
  - id: mo-unsafe-ptr
    name: Unsafe pointer arithmetic
    severity: error
    category: memory_safety
    pattern: 'unsafe\s*\{'
    message: Unsafe blocks bypass Mojo's memory safety guarantees
    fix_hint: Use safe references or the borrow checker
  - id: mo-var-overuse
    name: Overuse of var instead of let
    severity: warning
    category: code_quality
    pattern: '\bvar\s+\w+'
    message: Use 'let' for immutable bindings by default, 'var' only when mutation needed
    fix_hint: Replace var with let where the value doesn't change
```

## 集成方式

规则生成后:
1. 临时存储在 `~/.jcode/governance/languages/{lang}/rules.d/anti_patterns.yml`
2. 优先级低于内置规则，高于通用规则
3. 下次相同语言检查时自动加载
4. 用户可手动编辑优化
