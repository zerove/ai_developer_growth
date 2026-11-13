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

### `security_patterns.py` 已删除

`tools/scripts/rules_engine/security_patterns.py` **已被删除**（提交 `d439821`，
决策记录见 [ADR-059](../adr/ADR-059-security-patterns-dual-implementation.md)）。

该文件与 `rule_loader.py` 中的 `security_patterns` 字典构成同一概念的两份并行实现
（Python dict vs YAML），且冲突的规则 ID 命名从未被任何生产路径加载。删除前状态是
"零生产引用"，并非"仍在但不在加载路径上"。

新增跨语言安全规则请改 `ai-dev-framework/common/security.yml`。

### 自定义规则覆盖

优先级（高→低）：
1. `~/.config/adg/rules.yml`（用户全局）
2. `.adg/rules.yml`（项目级）
3. `.ai-rules/*.yml`（旧版目录级）
4. YAML 语言规则（框架内置，含 `common/security.yml`）

### 语言规则替代 common 规则

语言规则可用 `supersedes` 声明替代 `common/security.yml` 中的规则：

```yaml
- id: py-eval-exec
  supersedes:
  - common-eval-exec
```

加载时 `rule_loader` 会跳过被替代的 common 规则，避免同一 pattern 在同一行
重复报告；未声明 `supersedes` 的 common 规则仍正常合并。`ai-dev-framework`
的 `scan.py` 使用同一语义，保证两套扫描入口结果一致。

### 规则 ID 命名与碰撞检查

- 规则 ID 全局唯一，语言前缀必须无歧义。26/26 个语言已严格标准化，前缀统一由
  `rule_id_prefix()` 生成：Java/JavaScript/Ruby/Rust/TypeScript 使用
  `java-`/`js-`/`rb-`/`rs-`/`ts-`，Clojure/C++/Dart/Elixir/Haskell/Kotlin/Lua/
  PHP/PowerShell/Zig/Assembly/Fortran/GraphQL/MATLAB/Perl 使用
  `clj-`/`cpp-`/`dt-`/`ex-`/`hs-`/`kt-`/`lua-`/`php-`/`ps-`/`zig-`/`asm-`/
  `for-`/`gql-`/`mcl-`/`pl-`，C#/Go/Python/R/Scala/Swift 使用
  `cs-`/`go-`/`py-`/`r-`/`sc-`/`sw-`。旧的 `ja-*` / `ru-*` / `ruby-*` /
  `ty-*` / `cl-*` / `da-*` / `el-*` / `ha-*` / `cp-*` / `ko-*` / `lu-*` /
  `ph-*` / `po-*` / `zi-*` / `as-*` / `fo-*` / `gr-*` / `ma-*` / `pe-*`
  前缀已退役（2026-10-29），项目级 `.adg/rules.yml` 覆盖请改用新 ID。决策见
  [ADR-080](../adr/ADR-080-canonical-rule-id-prefix.md)。
- `tests/test_rule_supersedes_validation.py` 校验 `supersedes` 的类型、目标存在性、
  自引用与循环。
- `python -m tools.scripts.check_rule_collisions` 检查重复 ID 和未声明的跨源
  pattern 重叠；`tests/test_rule_collisions.py` 在 CI 中执行同一检查。
- `supersedes` 只影响 common 合并，不会删除用户自定义规则；语言规则的 pattern
  必须是 common 规则的超集，否则会丢失覆盖。

## 设计说明

- 规则来源收敛为单一 YAML 体系，避免同一规则在 Python 与 YAML 两处各维护一份
  （历史上 `security_patterns.py` 与 `common/security.yml` 规则 ID 命名不一致：
  `security-eval-exec` vs `common-eval-exec`）
- 自定义覆盖在加载时按优先级 merge，不修改源文件
