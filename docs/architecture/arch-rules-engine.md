---
title: "架构规则引擎设计"
description: "在现有规则引擎基础上，增加跨文件的架构分析能力。"
category: 工具层
tags: ['架构规则引擎设计', '差距', '的解决方案设计', '当前规则引擎只在单文件级别运作', '无法评估模块间关系', '分层违规']
difficulty: 基础
---

# 架构规则引擎设计

> 差距 5 的解决方案设计。当前规则引擎只在单文件级别运作，
> 无法评估模块间关系、分层违规、依赖方向等架构属性。

---

## 目标

在现有规则引擎基础上，增加跨文件的架构分析能力。

## 设计

### 核心思路

```
单文件检查 (现有)             跨文件分析 (新增)
┌─────────────┐              ┌──────────────────┐
│ checker.py  │              │ arch_checker.py  │
│ → 单文件模式 │              │ → 模块依赖图      │
│ → 正则匹配   │              │ → 分层关系分析     │
│ → AST 分析   │              │ → 循环依赖检测     │
└─────────────┘              └──────────────────┘
```

### 模块架构

```
tools/scripts/rules_engine/
├── arch/
│   ├── __init__.py
│   ├── dependency_graph.py    ← 构建模块依赖图
│   ├── layer_checker.py       ← 分层违规检测
│   └── cohesion_analyzer.py   ← 内聚性分析
```

### dependency_graph.py

从 import 语句构建完整的模块依赖图。

```python
class DependencyGraph:
    def build(self, root_dir: Path) -> Graph:
        """扫描所有源文件，构建依赖图"""

    def find_cycles(self) -> list[Cycle]:
        """检测循环依赖"""

    def find_violations(self, rules: LayerRules) -> list[Violation]:
        """检测分层违规"""
```

### layer_checker.py

定义分层规则并检测违规。

```yaml
# .adg/architecture.yml
layers:
  - name: controller
    allowed_deps: [service]
  - name: service
    allowed_deps: [repository, domain]
  - name: repository
    allowed_deps: [domain]
  - name: domain
    allowed_deps: []
```

### 与当前引擎的集成

| 集成点 | 方式 |
|--------|------|
| `check_directory()` | 在文件级检查后，运行架构检查 |
| `check_file()` | 单文件不涉及架构，不修改 |
| 输出格式 | 复用 `Issue` 模型，category="architecture" |
| CLI | `adg check --arch` 触发架构检查 |

## 优先级

| 功能 | 预估 | 优先级 |
|------|------|--------|
| import 依赖图构建 | 3h | P0 |
| 分层违规检测 | 2h | P1 |
| 模块内聚性度量 | 3h | P2 |
| 架构规则 YAML 配置 | 1h | P1 |
