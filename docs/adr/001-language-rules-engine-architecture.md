---
title: ADR-001b: 语言规则引擎架构设计
description: ADR-001b: 语言规则引擎架构设计 - 技术文档
category: 治理层
tags: ['ADR', '001b', 'architecture', 'rules-engine']
difficulty: 高级
reading_time: 10 分钟
updated: 2026-07-23
---

# ADR-001b: 语言规则引擎架构设计

## 状态
已通过

## 日期
2026-07-23

## 上下文

需要一个多语言代码质量验证系统：
- 支持 26+ 语言，使用 YAML 定义规则
- 通过 LSP 提供实时 IDE 反馈
- 集成到 CI/CD 流水线
- 允许项目自定义规则
- 生成多种报告格式

## 决策

采用**单体引擎 + 模块化内部结构**：

```
tools/scripts/
  _common.py              # 共享工具（路径、哈希、YAML）
  validate_language_rules.py  # 核心引擎（2160 行）
  detect_language.py      # 从文件扩展名检测语言
  ai_quality_gate.py      # jcode 流水线集成
  # 领域特定工具：
  rule_marketplace.py     # 规则包管理
  rule_author.py          # 规则创建 CLI
  rule_tracker.py         # 效果追踪
  rule_registry.py        # 中心注册表
  generate_fixes.py       # AI 辅助修复生成
  validate_rule_tests.py  # 正则测试框架
  git_diff_incremental.py # Git diff 集成
  rule_visualize.py       # Web UI
  rule_editor.py          # 实时编辑器
```

### 关键设计选择

1. **YAML 作为规则格式**：人类可读、可 diff、工具友好
2. **基于正则的模式匹配**：简单、快速、跨语言
3. **纯 Python 引擎**：无外部运行时依赖（仅 pyyaml）
4. **子进程用于 IDE 集成**：LSP 服务器调用 validate_language_rules.py
5. **基于文件的缓存**：MD5 哈希用于增量验证

## 影响

### 正面

- 单一语言（Python）用于所有工具
- 添加新语言简单（仅需添加 YAML）
- 无需编译步骤
- 离线可用

### 负面

- 2160 行主文件难以导航
- 纯正则规则遗漏部分模式（如控制流）
- 大多数语言无类型感知分析（仅 Python AST 支持）

## 考虑的替代方案

1. **基于 Tree-sitter**：功能更强但需要原生依赖
2. **原生 LSP**：需要各语言 LSP 服务器
3. **插件架构**：更灵活但更复杂

## 后续工作

- 将 validate_language_rules.py 拆分为模块（ADR-002b）
- 为 Python/TypeScript 深度分析添加 tree-sitter 支持（未来）