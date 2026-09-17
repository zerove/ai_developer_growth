# ADR-055: Phase 35 大文件 facade 拆分（6 文件 <850 行）

## 状态
接受

## 日期
2026-09-15

## 背景

ADR-038 复杂度治理设定"单文件 ≤ 850 行"门槛，但 adg CLI 尚未实施 cc 门禁（Phase 36a），且 6 个文件超限最多达 2.2×（language_registry.py 1898 行）。这些文件职责混杂（数据常量 + 注册表 + CLI 入口、扫描器 + 模型 + SBOM 生成、大单类 + 报告函数），继续膨胀将显著恶化可导航性与测试定位成本。

采用 **facade re-export 拆分**（沿用 ADR-014 的 ast_nodes.py 先例）：原文件保留全部公开 API 与导入路径，实现按职责落入同目录子模块，原文件变薄为显式 re-export facade。

## 决策

### 决策 1: 6 个文件按职责拆分，全部收敛 <850 行

| 原文件（行数） | 拆后 facade（行数） | 子模块 |
|---|---|---|
| `language_registry.py`（1898） | 252 | `_lang_types.py`(111 类)、`_lang_data_a.py`(796 前半常量)、`_lang_data_b.py`(671 后半常量+映射)、`_lang_registry.py`(246 注册表+函数) |
| `rules_engine/ast_parser.py`（1260） | 275 | `_ast_utils.py`(161 静态辅助+缓存)、`_ast_walkers.py`(846 按语言分组 mixin) |
| `supply_chain.py`（1190） | 86 | `_sc_models.py`(142 数据类)、`_sc_sbom.py`(617 SBOMGenerator)、`_sc_scanners.py`(436 扫描器) |
| `analyze_case_quality.py`（919） | 24 | `_case_quality.py`(769 大单类)、`_case_report.py`(140 报告+CLI) |
| `rules_engine/checker.py`（908） | 514 | `_checker_workers.py`(83)、`_checker_markers.py`(176)、`_checker_noqa.py`(100)、`_checker_linters.py`(89) |
| `exception_manager.py`（851） | 803 | `_exception_models.py`(90 数据类) |

- `language_registry.py` 数据常量按字母序两分（Python→Kotlin / Scala→SQL）以避免单模块再超限；依赖方向 `types ← data ← registry ← facade`。
- `ast_parser.py` 的 walk/parse 私有方法按语言分组为 **mixin 类**（`_ImportWalkers ← _FunctionWalkers ← _ClassWalkers`），`ASTParser` 以 `class ASTParser(_ClassWalkers, _FunctionWalkers, _ImportWalkers)` 继承，公共 API 与 MRO 语义不变；`_count_nodes` 下沉 `_ast_utils`，mixin 提供 1 行转发。
- `checker.py` 本可连 facade 一起瘦身，但 16 个私有符号被测试直接 import，故保持主流程在 facade，仅 worker/marker/noqa/linter 四组下沉。

### 决策 2: facade 以 `X as X` 自体别名显式 re-export（mypy strict 适配）

所有重导出采用 `from ._sub import X as X`（或逐条独立 import），满足 `no_implicit_reexport`；`__all__` 列出全部公开名。测试直接 import 的私有符号（如 checker 的 `_check_files_serial`/`_detect_language` 等 16 个）同样以别名形式保留出口。

### 决策 3: 模块级属性副效应保留

`supply_chain.py` 保持 `import subprocess` 顶层可见（`test_supply_chain_round2.py` 通过 `tools.scripts.supply_chain.subprocess.run` 打 patch）；`run_supply_chain_scan`/`generate_sbom` 便捷函数留在 facade。

## 后果

### 正面
- 6 个超限文件全部 <850 行（最大 facade exception_manager 803）；16 个子模块均 <850（最大 `_ast_walkers` 846 / `_lang_data_a` 796）
- **零行为变更**：全部为纯搬移；公开 API、导入路径、patch 目标、顺序语义逐一保留
- 可导航性提升：ast_parser 的 mixin 依赖链在模块 docstring 显式记录；checker 按门禁组（worker/marker/noqa/linter）分模块
- 外部导入方（hooks/*、jcode_cli、dependency_graph、parsers/*、validators/* 等）零改动

### 负面
- tools/scripts 的 .py 文件数 192 → **208**（+16 子模块），`test_semantic_checker_total_lines` 两个硬编码断言失效（`files_analyzed==192`、`ast_parser>1000 行`），已同步更新（208 / 改测 `_lang_data_a.py` 大文件样例）
- ruff isort 将 `X as X` 别名 re-export 拆为逐条独立 import 语句（`combine-as-imports=false` 仓库默认），facade 头部略冗长（已接受规范输出）

## 验证

- 拆分验收：6 facade + 16 子模块全部 <850 行；全部公开符号 + 测试私有符号 import 冒烟通过
- 相关性测试：ast_parser 系 129 / checker 系 205+19 / language_registry 23 / supply_chain 130 / analyze_case_quality 32 / exception_manager 78 全过（含 `_count_nodes` 迁移与 mixin 转发回归）
- mypy `tools/scripts/`: **0 issues / 208 files**
- ruff check / format: 本次全部新增/改动文件全过；全仓库仅剩 3 I001 + 2 format = **HEAD 基线预存**（`git show HEAD:file` 复现，ruff 版本漂移）
- adg check: **✓ 0 issues / 208 files**
- 全量 pytest: **4000 passed, 1 failed**（仅 `test_skips_skipped_results`，ADR-053 断言过期预存；原 3 个 link_auditor 环境失败随 session-state.md 产物消失而自愈）

## 累计状态

- 55 ADR（含本 ADR）
- 6 文件 7026 → 1954 行 facade（净 -5072 行单文件超限）+ 16 子模块 5473 行；单文件最大 846
- 全量 4000 tests passed（1 预存失败待另行处理）
- 待办：Phase 36（adg cc 门禁 + 18 个 ≥10cc 函数重构）