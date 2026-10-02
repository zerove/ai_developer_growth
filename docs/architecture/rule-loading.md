---
title: "规则加载架构"
description: "YAML 规则文件                       Python 硬编码规则"
category: 工具层
tags: ['规则加载架构', '规则来源收敛', '规则文件', 'YAML']
difficulty: 基础
---

# 规则加载架构

## 单一加载路径

跨语言安全规则已合并到 `common/security.yml`，**不再存在第二条 Python 硬编码加载路径**。

```
YAML 规则文件
(ai-dev-framework/languages/ + common/)
         │
         ▼
    rule_loader.py  ─── merge ───►  语言规则 + 框架规则 + common/security.yml
         │
         ▼
    load_rules_for_language()
         │
         ▼
    anti_pattern_checker.py
    naming_checker.py
    complexity_checker.py
```

### 路径说明

- 位置: `ai-dev-framework/languages/{lang}/rules.d/anti_patterns.yml`
  与 `ai-dev-framework/common/security.yml`
- 格式: YAML，含 `anti_patterns`、`naming`、`thresholds` 三节
- 加载: `rule_loader.load_rules()` → 内存缓存 + 磁盘缓存
- 合并: 语言规则 + 框架规则 + 通用安全规则（全部来自 YAML）

### `security_patterns.py` 的状态

`tools/scripts/rules_engine/security_patterns.py` **已废弃，不在加载路径上**。
`rule_loader.load_rules_for_language()` 不再调用它（见该函数 docstring）。
文件仅作为历史参考保留，其 `get_security_rules()` 不参与任何规则合并。

新增跨语言安全规则请改 `ai-dev-framework/common/security.yml`。

### 自定义规则覆盖

优先级（高→低）：
1. `~/.config/adg/rules.yml`（用户全局）
2. `.adg/rules.yml`（项目级）
3. `.ai-rules/*.yml`（旧版目录级）
4. YAML 语言规则（框架内置，含 `common/security.yml`）

## 设计说明

- 规则来源收敛为单一 YAML 体系，避免同一规则在 Python 与 YAML 两处各维护一份
  （历史上 `security_patterns.py` 与 `common/security.yml` 规则 ID 命名不一致：
  `security-eval-exec` vs `common-eval-exec`）
- 自定义覆盖在加载时按优先级 merge，不修改源文件
