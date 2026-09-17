# ADR-056: Phase 36 cc 门禁落地 + 18 个 ≥10cc 函数全量拆分

## 状态
接受

## 日期
2026-09-17

## 背景

ADR-038 复杂度治理设定 cc 门槛（函数 cyclomatic complexity ≤ 10），但 adg CLI 当时未实施 cc 门禁。Phase 36a 新建 `adg check --complexity` 能力并锁定 test_adg_cc_gate（6 测试）后，对 `tools/scripts` 全目录扫描，检出 **18 个函数 ≥10cc**（最高者含嵌套逻辑达 10+）。这些高复杂度函数状态分支交错、难以单测、难以导航，与治理目标冲突。

采用**门禁先行 + 逐个拆分**流程：36a 建 cc 门禁 → 36b 拆分 7 个函数 → 36c 拆分 11 个函数 → 全目录 cc 收敛至 0。

## 决策

### 决策 1: 嵌套函数必须拆为模块级 helper

cc analyzer 将嵌套函数体计入外层函数（实例：`dependency_graph._run_tarjan_scc` = 自身 2 + 嵌套 `_strongconnect` 8 = 10）。因此拆出的逻辑一律放**模块级**，不能在方法内再嵌套；拆分统一为"复杂函数变薄 + 模块级私有 helper 承载分支"模式。

### 决策 2: 18 个函数拆分清单（36b 7 + 36c 11）

| 阶段 | 函数 | 拆出的模块级 helper |
|---|---|---|
| 36b | `fix_heuristics._try_message_heuristics` | 3 个 heuristic helper |
| 36b | `jcode_cli._list_standalone_scripts` | `_classify_script` 等 |
| 36b | `update_ai_tool_matrix.update_matrix` | 映射/条目 helper |
| 36b | `rules_engine/plugins.discover_plugins` | 插件发现 helper |
| 36b | `adg_cli/check.py::check_file` | 结果组装 helper |
| 36b | `rules_engine/checker.py::check_file` | 语言/结果 helper |
| 36b | `dependency_graph._run_tarjan_scc` | `_tarjan_scc` + `_strongconnect` |
| 36c | `adg_cli/commands/cmd/_shared._load_rules_from_file` | `_parse_rule_file_simple` |
| 36c | `config/loader._deep_merge` | `_merge_lists` |
| 36c | `hooks/basic_checks._tests_for_modules` | `_matches_module` |
| 36c | `hooks/domain_checks._apply_baseline_ratchet` | `_filter_file_against_baseline` |
| 36c | `hooks/domain_checks._build_governance_checks` | `_option_governance_checks` + `_default_governance_checks` |
| 36c | `link_auditor.find_broken_links_with_index` | `_scan_markdown_file` |
| 36c | `rule_marketplace._show_pack_examples` | `_print_file_examples` + `_print_dir_examples` |
| 36c | `rules_engine/auto_fix.apply_fixes_to_directory` | `_resolve_file_lang` |
| 36c | `rules_engine/pattern_learner._collect_function_names` | `_classify_function_name`（模块级） |
| 36c | `rules_engine/quality_trends._generate_recommendations` | `_metric_regression_message` |
| 36c | `rules_engine/rule_docs_mapper.extract_keywords_from_rule` | `_id_part_keywords` + `_field_keywords` |

### 决策 3: 行为零变更

- 全部为纯结构拆分：公开 API、导入路径、调用点、顺序语义不变
- `fix_heuristics._try_message_heuristics` 保留 dirty 行（他人未提交改动约束）
- `_shared._parse_rule_file_simple` 为内部 helper，不加入 `__all__`
- 复用既有 helper（`link_auditor._is_skippable_target`）而非重复实现

## 后果

### 正面
- `adg check tools/scripts --complexity`: **18 errors → 0 errors**（全目录 cc≤10 收敛）
- 新增 ~17 个模块级私有 helper，每个可独立单测；文件名/职责边界更清晰
- test_adg_cc_gate 目录扫描测试改用 tmp_path fixture（`test_directory_scan_reports_cc_error`），不再依赖 repo 内文件，36c 期间保持绿

### 负面
- 模块级私有符号数量增加（~17 个）
- `domain_checks._build_governance_checks` 拆分力度比其他函数大（二次拆分 `_option_governance_checks` 才收敛到 cc<10，因 `if full or X` 每个 `or` 计一次决策）

## 验证

- `adg check tools/scripts --complexity`: **0 errors**（36c 收口）
- `test_adg_cc_gate.py`: **6 passed**（含改名后的 `test_directory_scan_reports_cc_error`）
- 相关模块测试 523 passed：_shared/loader 系 229 + basic/domain 系 84 + link/marketplace 82 + auto_fix/pattern 75 + trends/mapper 53
- adg 套件（bootstrap/checker_refactor）60 passed + 1 预存失败
- mypy: 10 个改动文件 **0 issues**（strict）
- ruff check / format: 改动文件全过
- 全量 pytest: **4006 passed, 1 failed**（仅 `test_skips_skipped_results`，ADR-053 断言过期预存，非回归）

## 累计状态

- 56 ADR（含本 ADR）
- cc 门禁落地：`tools/scripts` 全目录 cc≤10（0 errors）
- 18 个 ≥10cc 函数全量拆分完成（36b + 36c）
- 全量 4006 tests passed（1 预存失败待另行处理）
- 待办：Phase 34-36 收口汇报与 git commit 授权