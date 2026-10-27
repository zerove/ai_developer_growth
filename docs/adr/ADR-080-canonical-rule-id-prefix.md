# ADR-080: 规则 ID 前缀必须来自共享规范映射，不得由语言名截断推导

## 状态

接受

## 日期

2026-10-28

## 影响组件

- `tools/scripts/_common.py`
- `tools/scripts/rules_engine/rule_loader.py`
- `tools/scripts/rules_engine/validators/pipeline.py`
- `tests/test_common.py`
- `tests/test_pipeline_checker_ruleloader.py`
- `tests/test_rule_loader.py`
- `tests/test_validators_pipeline.py`

## 背景

规则治理硬化时，`ai-dev-framework/languages/*/rules.d` 的规则 ID 已统一到规范前缀：

- Rust 使用 `rs-`
- Java 使用 `java-`
- JavaScript 使用 `js-`
- Ruby 使用 `ruby-`
- TypeScript 使用 `ts-`

但 `_get_embedded_rules()` 的两个实现仍用 `language[:2]` 生成 fallback ID，
于是同一个语言在 YAML 可用与不可用时得到不同 ID：

- Rust: YAML `rs-eval-exec`，fallback `ru-eval-exec`
- Java: YAML `java-eval-runtime`，fallback `ja-eval-exec`
- JavaScript: YAML `js-eval`，fallback `ja-eval-exec`
- Ruby: YAML `ruby-eval`，fallback `ru-eval-exec`
- TypeScript: YAML `ts-eval`，fallback `ty-eval-exec`

fallback 不是死代码：规则目录缺失、安装不完整或测试隔离时都会走到这里。
ID 一旦分叉，`supersedes`、规则抑制、auto-fix 映射和问题追溯都会失配。
`tests/test_pipeline_checker_ruleloader.py` 原本还断言了 `ru-eval-exec`，
把错误行为锁成了预期。

## 决策

在 `tools/scripts/_common.py` 增加唯一的规范前缀表 `RULE_ID_PREFIXES`
和查询函数 `rule_id_prefix(language)`。两个 `_get_embedded_rules()` 实现
都改用该函数，不再自行截断语言名。

支持的 26 种语言以 `ai-dev-framework/languages/*/rules.d` 的实际前缀为准；
未知语言保留“取前两个字符”的 best-effort 行为，避免扩大变更范围。
测试同时覆盖代表性语言和“映射表与 YAML 实际 ID 一致”的漂移守卫。

## 后果

### 正面

- YAML 可用与 fallback 两条路径生成相同的规则 ID。
- 前缀规则只有一个来源，修复了 `ru-`、`ja-`、`ty-` 这类隐性分叉。
- 测试不再把错误 ID 锁成契约，新增语言时能发现映射漂移。

### 负面 / 代价

- 新增语言时必须同步更新 `RULE_ID_PREFIXES`，否则漂移测试会失败。
- 未知语言仍使用截断前缀，属于兼容性兜底，不是完整支持。
