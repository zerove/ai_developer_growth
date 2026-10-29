# ADR-080: 规则 ID 前缀必须来自共享规范映射，不得由语言名截断推导

## 状态

接受

## 日期

2026-10-28

## 影响组件

- `tools/scripts/_common.py`
- `tools/scripts/rules_engine/rule_loader.py`
- `tools/scripts/rules_engine/validators/pipeline.py`
- `tools/scripts/complexity_analyzer.py`
- `tools/scripts/naming_analyzer.py`
- `ai-dev-framework/languages/assembly/rules.d/anti_patterns.yml`
- `ai-dev-framework/languages/clojure/rules.d/anti_patterns.yml`
- `ai-dev-framework/languages/cpp/rules.d/anti_patterns.yml`
- `ai-dev-framework/languages/dart/rules.d/anti_patterns.yml`
- `ai-dev-framework/languages/elixir/rules.d/anti_patterns.yml`
- `ai-dev-framework/languages/fortran/rules.d/anti_patterns.yml`
- `ai-dev-framework/languages/graphql/rules.d/anti_patterns.yml`
- `ai-dev-framework/languages/haskell/rules.d/anti_patterns.yml`
- `ai-dev-framework/languages/kotlin/rules.d/anti_patterns.yml`
- `ai-dev-framework/languages/lua/rules.d/anti_patterns.yml`
- `ai-dev-framework/languages/matlab/rules.d/anti_patterns.yml`
- `ai-dev-framework/languages/perl/rules.d/anti_patterns.yml`
- `ai-dev-framework/languages/php/rules.d/anti_patterns.yml`
- `ai-dev-framework/languages/powershell/rules.d/anti_patterns.yml`
- `ai-dev-framework/languages/ruby/rules.d/anti_patterns.yml`
- `ai-dev-framework/languages/typescript/rules.d/anti_patterns.yml`
- `ai-dev-framework/languages/zig/rules.d/anti_patterns.yml`
- `tests/test_common.py`
- `tests/test_language_rules_languages_batch_c.py`
- `tests/test_pipeline_checker_ruleloader.py`
- `tests/test_rule_loader.py`
- `tests/test_validators_pipeline.py`
- `tests/test_rule_id_prefix_call_sites.py`
- `tests/test_language_rules_languages_dynamic.py`

## 背景

截至 2026-10-28，以下五个语言的规则 ID 已统一到规范前缀：

- Rust 使用 `rs-`
- Java 使用 `java-`
- JavaScript 使用 `js-`
- Ruby 使用 `rb-`
- TypeScript 使用 `ts-`

2026-10-29 完成 Batch A：Clojure、Dart、Elixir、Haskell 的 YAML ID 分别迁移到
`clj-`、`dt-`、`ex-`、`hs-`，退役 `cl-` / `da-` / `el-` / `ha-` 前缀。

2026-10-29 完成 Batch B：C++、Kotlin、Lua、PHP、PowerShell、Zig 的 YAML ID
分别迁移到 `cpp-`、`kt-`、`lua-`、`php-`、`ps-`、`zig-`，退役 `cp-` / `ko-` /
`lu-` / `ph-` / `po-` / `zi-` 前缀。

2026-10-29 完成 Batch C：Assembly、Fortran、GraphQL、MATLAB、Perl 的 YAML ID
分别迁移到 `asm-`、`for-`、`gql-`、`mcl-`、`pl-`，退役 `as-` / `fo-` /
`gr-` / `ma-` / `pe-` 前缀。

但 `_get_embedded_rules()` 的两个实现仍用 `language[:2]` 生成 fallback ID，
于是同一个语言在 YAML 可用与不可用时得到不同 ID：

- Rust: YAML `rs-eval-exec`，fallback `ru-eval-exec`
- Java: YAML `java-eval-runtime`，fallback `ja-eval-exec`
- JavaScript: YAML `js-eval`，fallback `ja-eval-exec`
- Ruby: YAML `rb-eval`，fallback `rb-eval-exec`
- TypeScript: YAML `ts-eval`，fallback `ty-eval-exec`

fallback 不是死代码：规则目录缺失、安装不完整或测试隔离时都会走到这里。
ID 一旦分叉，`supersedes`、规则抑制、auto-fix 映射和问题追溯都会失配。
`tests/test_pipeline_checker_ruleloader.py` 原本还断言了 `ru-eval-exec`，
把错误行为锁成了预期。

同样的截断还存在于 `complexity_analyzer.py` 和 `naming_analyzer.py`：
threshold/naming 规则 ID 也由 `language[:2]` 生成，Rust 得到 `ru-threshold-*`，
Java/JavaScript 得到 `ja-naming-*`，TypeScript 得到 `ty-threshold-*`。

## 决策

在 `tools/scripts/_common.py` 增加唯一的规范前缀表 `RULE_ID_PREFIXES`
和查询函数 `rule_id_prefix(language)`。两个 `_get_embedded_rules()` 实现，
以及 `complexity_analyzer.py`、`naming_analyzer.py`，都改用该函数，
不再自行截断语言名。

`RULE_ID_PREFIXES` 覆盖 26 个语言的候选前缀；全部 26 个语言的 YAML ID 已严格
校验。Batch C 完成后，Assembly、Fortran、GraphQL、MATLAB、Perl 使用 `asm-`、
`for-`、`gql-`、`mcl-`、`pl-`；C#、Go、Python、R、Scala、Swift 等原本
first-two 已对齐的语言也纳入 strict 守卫。未知语言保留“取前两个字符”的兼容
行为。测试同时覆盖代表性语言、标准化语言的完整前缀守卫，以及“映射表与 YAML
实际 ID 一致”的漂移检查。

## 后果

### 正面

- YAML、fallback、threshold 和 naming 路径生成相同的规则 ID。
- 前缀规则只有一个来源，修复了 `ru-`、`ja-`、`ty-` 这类隐性分叉。
- 测试不再把错误 ID 锁成契约，新增语言时能发现映射漂移。

### 负面 / 代价

- 新增语言时必须同步更新 `RULE_ID_PREFIXES`，否则漂移测试会失败。
- 未知语言仍使用截断前缀，属于兼容性兜底，不是完整支持。

## 修订记录

- 2026-10-29: Batch A 完成 Clojure (`clj-`)、Dart (`dt-`)、Elixir (`ex-`)、
  Haskell (`hs-`) 的规则 ID 迁移；退役 `cl-` / `da-` / `el-` / `ha-` 前缀，
  标准化语言从 5 个扩展到 9 个。
- 2026-10-29: Batch B 完成 C++ (`cpp-`)、Kotlin (`kt-`)、Lua (`lua-`)、
  PHP (`php-`)、PowerShell (`ps-`)、Zig (`zig-`) 的规则 ID 迁移；退役
  `cp-` / `ko-` / `lu-` / `ph-` / `po-` / `zi-` 前缀，标准化语言从 9 个扩展到
  15 个。
- 2026-10-29: Batch C 完成 Assembly (`asm-`)、Fortran (`for-`)、GraphQL (`gql-`)、
  MATLAB (`mcl-`)、Perl (`pl-`) 的规则 ID 迁移；退役 `as-` / `fo-` / `gr-` /
  `ma-` / `pe-` 前缀，并将 C#、Go、Python、R、Scala、Swift 纳入 strict 守卫，
  标准化语言从 15 个扩展到 26 个。
