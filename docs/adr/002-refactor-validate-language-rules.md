---
title: ADR-002b: 重构 validate_language_rules.py 模块化
description: ADR-002b: 重构 validate_language_rules.py 模块化 - 技术文档
category: 治理层
tags: ['ADR', '002b', 'refactor', 'rules-engine']
difficulty: 进阶
reading_time: 10 分钟
updated: 2026-07-23
---

# ADR-002b: 重构 validate_language_rules.py 模块化

## 状态
已通过

## 日期
2026-07-23

## 上下文

`validate_language_rules.py` 增长到 2166 行，包含 50 个函数，涵盖：
- 规则加载与合并
- 反模式检测
- 命名约定检查
- 复杂度分析
- Python AST 分析
- 自动修复引擎
- 报告生成（JUnit/HTML/SARIF）
- 健康度评分
- Linter 聚合
- 文件缓存

这导致难以导航、隔离测试和维护。

## 决策

重构为 `rules_engine/` 包，统一入口点 `hooks_runner.py`：

```
tools/scripts/rules_engine/
  __init__.py              # 公共 API + 文档示例
  models.py                # Issue, CheckResult, Severity, HealthScore
  rule_loader.py           # load_rules()、磁盘缓存、YAML 合并
  anti_pattern_checker.py  # 基于正则的反模式检测
  naming_checker.py        # 命名约定验证
  complexity_checker.py    # AST 复杂度（Python）+ 正则（JS/TS）
  security_patterns.py     # 跨语言安全/类型/错误模式
  checker.py               # 主编排器 + 外部 linter 集成

tools/scripts/hooks_runner.py    # 统一 CLI 入口点
tools/scripts/report_generator.py # JUnit/HTML/SARIF 报告生成
tools/scripts/fix_applier.py      # 自动修复引擎
```

### 迁移策略（已完成）

1. 创建 `rules_engine/` 包，包含模块化检查器
2. 创建 `hooks_runner.py` 作为统一入口点（lint、format、typecheck、test、security、quality-gate、governance-audit）
3. 从 validate_language_rules.py 提取 `report_generator.py` 和 `fix_applier.py`
4. 更新 `validate_language_rules.py` 委托给新模块（向后兼容）
5. 更新 CI/CD 使用 `hooks_runner.py`
6. 新增 82 个单元测试（748 -> 830 总计）

## 影响

### 正面

- 每个模块独立可测试（rules_engine 新增 55 个测试）
- hooks_runner.py 通过并行化缩短全检查时间（lint+format+typecheck 并发）
- 更清晰的依赖图
- 规则加载跨 CLI 调用的磁盘缓存
- CI/CD 和预提交钩子的统一入口点

### 负面

- 文件更多（7 个模块 vs 1 个单体）
- 导入路径变更（通过 validate_language_rules.py 的重新导出缓解）

## 指标

| 指标 | 重构前 | 重构后 |
|--------|--------|-------|
| validate_language_rules.py | 2166 行 | 1930 行 (-11%) |
| rules_engine 模块 | 0 | 7 个模块 |
| 测试数量 | 748 | 830 (+82) |
| hooks_runner.py | N/A | 560 行 |
| 报告生成器 | 内联 | 232 行 (report_generator.py) |
| 修复应用器 | 内联 | 85 行 (fix_applier.py) |
