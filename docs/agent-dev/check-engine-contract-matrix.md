# 检查引擎契约矩阵（adg check / rules_engine / hooks）

> 目的：在**不进行大重构**的前提下，明确 `adg_cli.check` 与 `rules_engine.checker` 的现状差异，
> 先锁定共享不变量，再决定是否/如何收敛实现。

## 路径与入口

| 维度 | `rules_engine.checker.check_directory` | `adg_cli.check.check_directory` | hooks `language-rules` |
|---|---|---|---|
| 入口 | `tools/scripts/rules_engine/checker.py` | `tools/scripts/adg_cli/check.py` | `tools/scripts/hooks/domain_checks.py`（默认）/ `hooks_runner._language_rules_cache`（`--cache`） |
| 返回 | `list[CheckResult]`（文件级结果 + issues） | `list[Issue]`（扁平 issues） | text / JSON 字符串（`passed`, `results`） |
| 规则加载 | `rules=None` 时自动加载 | 调用方传入 `rules`；`load_rules_for_language` 合并 common 安全规则并遵守 `supersedes` | 校验 language rules 资产 |
| 语言过滤 | `languages=[...]` | 由 `_detect_language_from_file` 决定 | `--lang` 参数 |
| 统计出参 | `stats=dict`（files_checked/parallel/cache_*） | 无 rules_engine stats；JSON `meta` 显式标记 `cache_supported=false`、`cache_reason` 且 `cache_*`/`cache_hit_rate` 为 `null` | JSON `meta`（`--cache` 分支） |
| 缓存 | `use_cache=True`（SQLite/`CheckStore`，串/并行真实统计） | 当前无 rules_engine cache 聚合（不臆造命中/缺失） | `--cache` 分支使用 `rules_engine.checker.check_directory` |
| 并行 | 文件数 >4 且 `jobs>1` 时走进程池；jobs 缺省取 `[tool.adg].jobs`（默认 4） | 文件数 >1 且 `jobs>1` 时并行；jobs 缺省取 `[tool.adg].jobs`（默认 4，P-01 2026-11-09） | 由 `--cache` 分支/配置决定 |
| 崩坏处理 | worker 异常/None 留痕（`failed_files`/degraded） | `check-error` Issue，fail-closed（ADR-078） | 由底层检查决定 |
| 语义/外部 linter | `semantic`/`run_linters` 开关 | 规则驱动；另有 AST/复杂度辅助检查 | 由 rules_engine 校验路径决定 |

## 已验证的共享不变量（fixture 实测）

输入：目录含 `a.py`（`print(...)`）、`b.py`（`eval(...)`）、`c.js`、`d.txt`；Python 过滤/规则。

- 两个实现都检查 `a.py`、`b.py`（不检查 `c.js`/`d.txt`）。
- 两个实现都产出核心规则：`py-eval-exec`、`py-print-statement`、`py-log-print`。
- 两个实现的 issue 集合一致（当前 fixture：3 vs 3）。
- **已收敛差异**：`adg_cli.rules.load_rules_for_language` 现与 `rules_engine._merge_common_rules`
  一样遵守语言规则的 `supersedes`，因此 `common-eval-exec` 不再与 `py-eval-exec` 重复上报；
  未被 supersede 的通用规则（如 JavaScript 的 `common-eval-exec`）仍保留。

> 结论：**文件覆盖、核心规则、issue 集合已对齐；统计/缓存出参与执行路径仍不一致**。
> `adg check` 已显式暴露 `cache_supported=false`、`cache_reason` 与空 `cache_*`（可观测性），但不提供 rules_engine 级缓存统计；
> 下游仍不应依赖两个入口的 stats 结构，但可依赖当前规则集下 issue 集合一致。

## 缓存可观测性词汇表（2026-11-12 对齐第一阶段）

三条路径对"缓存状态"使用同一套键名与语义，下游只依赖词汇表即可解读：

| 键 | 语义 | `rules_engine.checker` | `hooks --cache` | `adg check --json` |
|---|---|---|---|---|
| `use_cache` | 本次运行是否启用缓存 | `bool` | `bool` | `false` |
| `cache_supported` | 该路径是否具备缓存能力 | `true` | `true` | `false` |
| `cache_engine` | 缓存实现标识 | `rules_engine_check_store` | 同左 | `null` |
| `cache_initialized` | 缓存存储是否就绪 | `bool` | `bool` | `false` |
| `cache_reason` | 不可用/未启用原因；可用且已启用时 `null` | `null` / `cache_disabled` | 同左 | `adg_cli_path_no_rules_engine_cache` |
| `cache_hits` / `cache_misses` | 真实命中/缺失计数 | 启用时为整数 | 同左 | `null` |
| `cache_degraded` | 缓存降级次数 | 启用时为整数 | 同左 | `null` |
| `cache_hit_rate` | `hits/(hits+misses)` | 启用时为 `float` | 同左 | `null` |

**不臆造 0**：计数不可知（缓存未启用、目录不存在、无缓存操作）一律 `null`。
0 会被下游读成"缓存全未命中"，与"没有缓存"是两种不同事实。

> 契约由 `tests/test_cache_observability_contract.py` 锁定（键存在性 + 语义）。

## 收敛建议（渐进）

1. 保持本矩阵随行为变化更新；新增差异先记录再修复。
2. 为共享不变量补契约测试（文件覆盖、核心规则、崩坏留痕、exit 语义）。
3. 若要让 `adg check` 复用 rules_engine：优先把 `adg_cli.check` 的通用规则/AST/复杂度能力
   上移为引擎可选模块，CLI 仅保留参数/输出/兼容层；分阶段迁移并以本矩阵+测试守护。
4. 缓存能力的**执行路径**统一（而非仅字段统一）留待第二阶段：需先决定
   `adg check` 是否引入 `CheckStore`，该决策会改变 CLI 行为与磁盘产物，须单独立项。
