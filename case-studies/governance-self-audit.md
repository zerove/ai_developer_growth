---
title: 用自己的药医自己——ai-dev-framework 实战验证记
description: 用 ai-dev-framework 治理 ai_developer_growth 项目自身代码，发现 85 个质量问题的经验与洞察
category: 治理层
tags: ['治理', '实战', 'ai-dev-framework', '质量门禁']
difficulty: 中级
reading_time: 8 分钟
updated: 2026-07-29
---

# 用自己的药医自己——ai-dev-framework 实战验证记

> **背景**: ai_developer_growth 项目构建了一套完整的 AI 治理框架 (ai-dev-framework)，
> 包含质量门禁、语言规则、钩子系统等能力。但"自己的刀能否削自己的把"？
> 我们用框架自带的 quality-gate 对项目自身的 `tools/` 目录进行了一次完整审计。

---

## 审计配置

- **审计工具**: `tools/scripts/hooks_runner.py quality-gate`
- **审计范围**: `tools/scripts/` 目录下的所有 Python 文件（105 个文件）
- **检查维度**: 安全模式、反模式、类型注解、命名规范、复杂度
- **执行时间**: 约 2 秒

## 审计结果

| 指标 | 数值 |
|------|------|
| 检查文件数 | 105 |
| 通过 | 81 个文件 |
| 未通过 | 24 个文件 |
| 总问题数 | 85 个 |

### 问题分类

| 类别 | 数量 | 严重程度 |
|------|------|----------|
| 使用 MD5 不安全哈希 | 4 | 🔴 中 |
| 使用 `Any` 类型 | ~78 | 🟡 低 |
| 使用 `eval`（误报） | 1 | 🟢 无风险 |
| 其他 | 2 | 🟡 低 |

## 修复措施

### 已修复: MD5 → SHA256

4 处 MD5 用于文件缓存哈希，虽非安全用途，仍升级为 SHA256：

| 文件 | 原因 | 修复 |
|------|------|------|
| `validate_language_rules.py` | 文件变更检测缓存 | `md5()` → `sha256()` |
| `validators/cli.py` | 文件变更检测缓存 | `md5()` → `sha256()` |
| `validators/pipeline.py` | 规则文件 hash 缓存 | `md5()` → `sha256()` |
| `rules_engine/performance.py` | 文件变更检测缓存 | `md5()` → `sha256()` |

### 确认误报: `eval` 检测

`rule_editor.py` 中匹配到 `eval` 是因为一行 YAML 示例代码包含了 `ast.literal_eval()` 字符串，而非真正的 `eval()` 调用。

### 待评估: `Any` 类型

约 78 处 `Any` 类型主要分布在两个场景：

1. **tree-sitter AST 解析**（`ast_parser.py` 31 处）— tree-sitter 库本身返回 `Any`，强行标注具体类型需要创建复杂类型桩
2. **通用回退逻辑**（`checker.py`、`rule_loader.py` 等）— 多语言框架的通用层天然需要宽泛类型

## 关键洞察

### 1. 质量门禁真的能发现问题

如果不是这次审计，4 处 MD5 会一直存在于代码中。虽然缓存用途风险低，但统一升级为 SHA256 消除了安全隐患和审计噪音。

### 2. 规则引擎需要误报回馈机制

`eval` 误报暴露了一个系统性问题：规则引擎只能匹配字符串模式，无法区分"真正调用"和"示例代码"。目前的规则定义不够**上下文感知**。

### 3. `Any` 类型阈值需要调整

对于 tree-sitter 这类动态库封装层，100% 类型安全不现实。治理框架应该支持**准入例外声明**（allowlist）或**按模块调整阈值**。

### 4. 治理工具的开发者体验

`hooks_runner.py quality-gate` 执行一次只需 2 秒，输出清晰（通过/失败/问题数），开发者体验良好。这是能被团队接受的关键。

## 改进建议

| 改进项 | 优先级 | 说明 |
|--------|--------|------|
| 添加误报回馈通道 | P1 | 允许 Reviewer 标记误报，反馈到规则库 |
| 支持模块级例外声明 | P1 | 在 `pyproject.toml` 中声明允许 `Any` 的模块 |
| 类型覆盖率追踪 | P2 | 按模块统计类型覆盖率，而非简单地检查 `Any` 出现次数 |
| 降低审计噪音 | P1 | 对 tree-sitter 封装层自动豁免 `Any` 检查 |

## 相关资源

- [[ai-dev-framework/GOVERNANCE|治理标准]]
- [[tools/scripts/hooks_runner.py|钩子运行器]]
- [[tools/scripts/rules_engine/checker.py|规则检查器]]

---

*本案例由 governance-audit 工具自动发现，经人工验证后记录。*
