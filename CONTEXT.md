# 项目上下文

> Agent 会话启动时的项目级上下文。**固定头部区**（本段与后续直到第一个 `## 更新记录:` 之前）
> 由人工维护且不参与滚动窗口裁剪；下方 `## 更新记录:` 区由 `context-sync` 自动追加、按窗口裁剪。
> 结构约束见 ADR-061。

## 项目定位

AI 时代开发者成长知识库 + 治理框架（knowledge base + governance framework）。
核心原则**知识优先，工具为辅，案例验证** —— 见 [ROADMAP.md](ROADMAP.md) 愿景段落。

- 领域术语以 [UBIQUITOUS_LANGUAGE.md](UBIQUITOUS_LANGUAGE.md) 为唯一口径
- 治理标准以 [GOVERNANCE.md](GOVERNANCE.md) 为准（5 步闭环 + 4 道门禁）
- Agent 定义索引见 [AGENTS.md](AGENTS.md)，工作流配置见 [.jcode/AGENTS.md](.jcode/AGENTS.md)

## 项目状态

| 项 | 值 |
|---|---|
| 版本 | v2.24.0（`pyproject.toml`） |
| 语言 | Python 3.11+ 工具链 + Markdown 文档 |
| 源码规模 | `tools/scripts` + `.jcode/scripts` 共 220 个 `.py` 文件 |
| 测试规模 | 200 个测试文件，4495 passed |
| 覆盖率 | 87.82%（门禁阈值 80%，`cov_min`） |
| 类型检查 | mypy strict，233 source files clean |
| 代码风格 | ruff check + ruff format（944 files formatted） |
| ADR 累计 | 63 篇（`docs/adr/`；ADR-006 历史空号，ADR-040 为追补） |

## 核心目录

| 路径 | 职责 |
|---|---|
| `tools/scripts/` | 生产工具链（`adg` CLI、`jcode-cli`、rules_engine、hooks 等） |
| `.jcode/scripts/` | Skill 入口脚本（hooks 调度入口，多数无 `sys.path` 依赖） |
| `tests/` | 全部测试，按 `test_*.py` 收集 |
| `docs/adr/` | 架构决策记录单篇文件，索引在 `ADR.md` |
| `examples/` | 方法论参考实现（非生产代码，`ruff` 已排除） |

## 关键约束

- **门禁不可 fail-open**：任何校验失败必须让退出码非 0，否则在 hooks / CI 中形同虚设
  （ADR-057 CI 心跳、ADR-061 context-sync 校验均为同类教训）
- **CONTEXT.md 固定头部必须排在所有 `## 更新记录:` 之前**，否则滚动窗口裁剪会
  把项目上下文一并丢弃（ADR-061）
- **覆盖率门禁范围**：`tools/scripts` 与 `.jcode/scripts` 均在门禁内，`.jcode/scripts`
  曾长期在门禁之外造成静默劣化区（见 `pyproject.toml` `[tool.adg] cov_min` 注释）
- **ruff 版本锁定** 0.15.17：0.16+ 启用 2025 format style 会造成 CI 与本地结果不一致
- **不命名为 `jcode` 的 console_script**：会遮蔽 Rust 版 jcode TUI

## 决策记录

决策全文见 [ADR.md](ADR.md) 索引与 `docs/adr/`。影响本文件的决策：

- **ADR-061**: CONTEXT.md 固定头部独立于滚动窗口 + 校验不得 fail-open
- **ADR-058**: context-sync 双实现并存是刻意设计，不做合并
- **ADR-057**: CI 心跳检测必须跑在 CI 之外
- **ADR-056**: cc（圈复杂度）门禁落地，全目录 ≤10

## 计划

后续开发计划以 [ROADMAP.md](ROADMAP.md) 顶部 `## 当前状态` 段落为准（按会话倒序，最新在最前）。
变更历史以 [CHANGELOG.md](CHANGELOG.md) 为准。

---

## 更新记录: 2026-10-02 23:54:36

### 任务
Git 变更同步

### 变更摘要
- 变更文件 3 个 (+98 / -271 行)
  - .jcode/hooks.json
  - CONTEXT.md
  - uv.lock

## 更新记录: 2026-10-02 23:54:12

### 任务
Git 变更同步

### 变更摘要
- 变更文件 3 个 (+87 / -253 行)
  - .jcode/hooks.json
  - CONTEXT.md
  - uv.lock

## 更新记录: 2026-10-02 23:54:11

### 任务
Git 变更同步

### 变更摘要
- 变更文件 3 个 (+76 / -237 行)
  - .jcode/hooks.json
  - CONTEXT.md
  - uv.lock

## 更新记录: 2026-10-02 23:53:54

### 任务
Git 变更同步

### 变更摘要
- 变更文件 3 个 (+66 / -206 行)
  - .jcode/hooks.json
  - CONTEXT.md
  - uv.lock

## 更新记录: 2026-10-02 23:53:54

### 任务
Git 变更同步

### 变更摘要
- 变更文件 3 个 (+55 / -181 行)
  - .jcode/hooks.json
  - CONTEXT.md
  - uv.lock

## 更新记录: 2026-10-02 23:53:27

### 任务
Git 变更同步

### 变更摘要
- 变更文件 2 个 (+37 / -158 行)
  - CONTEXT.md
  - uv.lock

## 更新记录: 2026-10-02 23:53:27

### 任务
Git 变更同步

### 变更摘要
- 变更文件 2 个 (+27 / -148 行)
  - CONTEXT.md
  - uv.lock

## 更新记录: 2026-10-02 23:44:54

### 任务
Git 变更同步

### 变更摘要
- 变更文件 3 个 (+122 / -121 行)
  - CHANGELOG.md
  - ROADMAP.md
  - uv.lock

## 更新记录: 2026-10-02 23:36:35

### 任务
Git 变更同步

### 变更摘要
- 变更文件 9 个 (+621 / -467 行)
  - .jcode/scripts/context-sync.py
  - ADR.md
  - CONTEXT.md
  - pyproject.toml
  - requirements-dev.txt
  - tests/test_context_sync_prune.py
  - tests/test_coverage_gate_scope.py
  - tests/test_jcode_context_sync.py
  - uv.lock

## 更新记录: 2026-10-02 23:32:27

### 任务
Git 变更同步

### 变更摘要
- 变更文件 8 个 (+544 / -434 行)
  - .jcode/scripts/context-sync.py
  - CONTEXT.md
  - pyproject.toml
  - requirements-dev.txt
  - tests/test_context_sync_prune.py
  - tests/test_coverage_gate_scope.py
  - tests/test_jcode_context_sync.py
  - uv.lock

## 更新记录: 2026-10-02 23:32:07

### 任务
Git 变更同步

### 变更摘要
- 变更文件 8 个 (+521 / -401 行)
  - .jcode/scripts/context-sync.py
  - CONTEXT.md
  - pyproject.toml
  - requirements-dev.txt
  - tests/test_context_sync_prune.py
  - tests/test_coverage_gate_scope.py
  - tests/test_jcode_context_sync.py
  - uv.lock

## 更新记录: 2026-10-02 23:31:45

### 任务
Git 变更同步

### 变更摘要
- 变更文件 8 个 (+505 / -364 行)
  - .jcode/scripts/context-sync.py
  - CONTEXT.md
  - pyproject.toml
  - requirements-dev.txt
  - tests/test_context_sync_prune.py
  - tests/test_coverage_gate_scope.py
  - tests/test_jcode_context_sync.py
  - uv.lock

## 更新记录: 2026-10-02 23:28:21

### 任务
Git 变更同步

### 变更摘要
- 变更文件 6 个 (+342 / -312 行)
  - .jcode/scripts/context-sync.py
  - CONTEXT.md
  - pyproject.toml
  - requirements-dev.txt
  - tests/test_coverage_gate_scope.py
  - uv.lock

---

## 更新记录: 2026-10-02 23:10:06

### 任务
Git 变更同步

### 变更摘要
- 变更文件 5 个 (+269 / -269 行)
  - CONTEXT.md
  - pyproject.toml
  - requirements-dev.txt
  - tests/test_coverage_gate_scope.py
  - uv.lock

---

## 更新记录: 2026-10-02 17:56:27

### 任务
Git 变更同步

### 变更摘要
- 变更文件 4 个 (+239 / -126 行)
  - CONTEXT.md
  - pyproject.toml
  - requirements-dev.txt
  - tests/test_coverage_gate_scope.py

---

## 更新记录: 2026-10-02 17:53:31

### 任务
Git 变更同步

### 变更摘要
- 变更文件 4 个 (+225 / -107 行)
  - CONTEXT.md
  - pyproject.toml
  - requirements-dev.txt
  - tests/test_coverage_gate_scope.py

---

## 更新记录: 2026-10-02 17:49:44

### 任务
Git 变更同步

### 变更摘要
- 变更文件 43 个 (+966 / -352 行)
  - .jcode/hooks.json
  - AGENTS.md
  - CONTEXT.md
  - README.md
  - docs/architecture/rule-loading.md
  - docs/case-studies/ai-context-sync-development.md
  - docs/case-studies/ai-task-prioritizer.md
  - docs/case-studies/api-design-implementation.md
  - docs/case-studies/api-monitoring.md
  - docs/case-studies/cli-tool-development.md
  - docs/case-studies/data-pipeline.md
  - docs/case-studies/database-migration.md
  - docs/case-studies/web-scraping-tool.md
  - examples/ai-context-sync/pyproject.toml
  - examples/ai-navigation-web/pyproject.toml
  - examples/ai-navigation/pyproject.toml
  - examples/ai-navigation/src/enhanced_tfidf.py
  - examples/self-correction-loop/src/runner.py
  - examples/self-correction-loop/src/strategies/pattern.py
  - examples/self-correction-loop/tests/conftest.py
  - ... 等共 43 个文件

---

## 更新记录: 2026-10-02 17:46:02

### 任务
Git 变更同步

### 变更摘要
- 变更文件 43 个 (+935 / -333 行)
  - .jcode/hooks.json
  - AGENTS.md
  - CONTEXT.md
  - README.md
  - docs/architecture/rule-loading.md
  - docs/case-studies/ai-context-sync-development.md
  - docs/case-studies/ai-task-prioritizer.md
  - docs/case-studies/api-design-implementation.md
  - docs/case-studies/api-monitoring.md
  - docs/case-studies/cli-tool-development.md
  - docs/case-studies/data-pipeline.md
  - docs/case-studies/database-migration.md
  - docs/case-studies/web-scraping-tool.md
  - examples/ai-context-sync/pyproject.toml
  - examples/ai-navigation-web/pyproject.toml
  - examples/ai-navigation/pyproject.toml
  - examples/ai-navigation/src/enhanced_tfidf.py
  - examples/self-correction-loop/src/runner.py
  - examples/self-correction-loop/src/strategies/pattern.py
  - examples/self-correction-loop/tests/conftest.py
  - ... 等共 43 个文件

---

## 更新记录: 2026-10-02 17:44:35

### 任务
Git 变更同步

### 变更摘要
- 变更文件 43 个 (+904 / -317 行)
  - .jcode/hooks.json
  - AGENTS.md
  - CONTEXT.md
  - README.md
  - docs/architecture/rule-loading.md
  - docs/case-studies/ai-context-sync-development.md
  - docs/case-studies/ai-task-prioritizer.md
  - docs/case-studies/api-design-implementation.md
  - docs/case-studies/api-monitoring.md
  - docs/case-studies/cli-tool-development.md
  - docs/case-studies/data-pipeline.md
  - docs/case-studies/database-migration.md
  - docs/case-studies/web-scraping-tool.md
  - examples/ai-context-sync/pyproject.toml
  - examples/ai-navigation-web/pyproject.toml
  - examples/ai-navigation/pyproject.toml
  - examples/ai-navigation/src/enhanced_tfidf.py
  - examples/self-correction-loop/src/runner.py
  - examples/self-correction-loop/src/strategies/pattern.py
  - examples/self-correction-loop/tests/conftest.py
  - ... 等共 43 个文件

---

## 更新记录: 2026-10-02 17:42:32

### 任务
Git 变更同步

### 变更摘要
- 变更文件 42 个 (+839 / -299 行)
  - .jcode/hooks.json
  - AGENTS.md
  - CONTEXT.md
  - README.md
  - docs/architecture/rule-loading.md
  - docs/case-studies/ai-context-sync-development.md
  - docs/case-studies/ai-task-prioritizer.md
  - docs/case-studies/api-design-implementation.md
  - docs/case-studies/api-monitoring.md
  - docs/case-studies/cli-tool-development.md
  - docs/case-studies/data-pipeline.md
  - docs/case-studies/database-migration.md
  - docs/case-studies/web-scraping-tool.md
  - examples/ai-context-sync/pyproject.toml
  - examples/ai-navigation-web/pyproject.toml
  - examples/ai-navigation/pyproject.toml
  - examples/ai-navigation/src/enhanced_tfidf.py
  - examples/self-correction-loop/src/runner.py
  - examples/self-correction-loop/src/strategies/pattern.py
  - examples/self-correction-loop/tests/conftest.py
  - ... 等共 42 个文件

---

## 更新记录: 2026-10-02 17:39:56

### 任务
Git 变更同步

### 变更摘要
- 变更文件 40 个 (+803 / -281 行)
  - .jcode/hooks.json
  - AGENTS.md
  - CONTEXT.md
  - README.md
  - docs/architecture/rule-loading.md
  - docs/case-studies/ai-context-sync-development.md
  - docs/case-studies/ai-task-prioritizer.md
  - docs/case-studies/api-design-implementation.md
  - docs/case-studies/api-monitoring.md
  - docs/case-studies/cli-tool-development.md
  - docs/case-studies/data-pipeline.md
  - docs/case-studies/database-migration.md
  - docs/case-studies/web-scraping-tool.md
  - examples/ai-context-sync/pyproject.toml
  - examples/ai-navigation-web/pyproject.toml
  - examples/ai-navigation/pyproject.toml
  - examples/ai-navigation/src/enhanced_tfidf.py
  - examples/self-correction-loop/src/runner.py
  - examples/self-correction-loop/src/strategies/pattern.py
  - examples/self-correction-loop/tests/conftest.py
  - ... 等共 40 个文件

---

## 更新记录: 2026-10-02 17:25:17

### 任务
Git 变更同步

### 变更摘要
- 变更文件 39 个 (+772 / -264 行)
  - .jcode/hooks.json
  - AGENTS.md
  - README.md
  - docs/architecture/rule-loading.md
  - docs/case-studies/ai-context-sync-development.md
  - docs/case-studies/ai-task-prioritizer.md
  - docs/case-studies/api-design-implementation.md
  - docs/case-studies/api-monitoring.md
  - docs/case-studies/cli-tool-development.md
  - docs/case-studies/data-pipeline.md
  - docs/case-studies/database-migration.md
  - docs/case-studies/web-scraping-tool.md
  - examples/ai-context-sync/pyproject.toml
  - examples/ai-navigation-web/pyproject.toml
  - examples/ai-navigation/pyproject.toml
  - examples/ai-navigation/src/enhanced_tfidf.py
  - examples/self-correction-loop/src/runner.py
  - examples/self-correction-loop/src/strategies/pattern.py
  - examples/self-correction-loop/tests/conftest.py
  - examples/self-correction-loop/tests/test_main.py
  - ... 等共 39 个文件

---

## 更新记录: 2026-09-18 00:16:18

### 任务
Git 变更同步

### 变更摘要
- 变更文件 20 个 (+144 / -216 行)
  - .github/workflows/adg-governance.yml
  - .github/workflows/adg-quality-report.yml
  - .github/workflows/adg-scan.yml
  - .github/workflows/advanced-governance.yml
  - .github/workflows/ai-native-sdlc.yml
  - .github/workflows/audit-to-pr.yml
  - .github/workflows/ci.yml
  - .github/workflows/community-case-pr.yml
  - .github/workflows/example-ci-template.yml
  - .github/workflows/jobs/combine-coverage.yml
  - .github/workflows/jobs/lint.yml
  - .github/workflows/jobs/setup.yml
  - .github/workflows/jobs/tests.yml
  - .github/workflows/language-rules.yml
  - .github/workflows/mutation-testing.yml
  - .github/workflows/quality-trends.yml
  - .github/workflows/release.yml
  - .github/workflows/scheduled-governance.yml
  - .github/workflows/slsa-provenance.yml
  - CONTEXT.md

---

## 更新记录: 2026-09-17 21:00:12

### 任务
Git 变更同步

### 变更摘要
- 变更文件 4 个 (+29 / -3 行)
  - agents/context-sync.md
  - agents/multi-agent-orch.md
  - agents/self-correction-loop.md
  - tests/test_adg_checker_refactor.py

---

## 更新记录: 2026-09-17 20:15:13

### 任务
Git 变更同步

### 变更摘要
- 变更文件 22 个 (+635 / -204 行)
  - .jcode/scripts/governance-auditor.py
  - CHANGELOG.md
  - CONTEXT.md
  - ROADMAP.md
  - docs/adr/ADR-054-phase-34-dedup-common.md
  - docs/adr/ADR-056-phase-36-complexity-gate.md
  - docs/adr/ADR.md
  - pyproject.toml
  - tests/conftest.py
  - tests/test_adg_bootstrap_unit.py
  - tests/test_check_directory_skipped.py
  - tests/test_language_rules_v2.py
  - tests/test_quality_gate_full.py
  - tests/test_rule_registry.py
  - tests/test_semantic_rules.py
  - tests/test_supply_chain_round2.py
  - tools/scripts/_sc_scanners.py
  - tools/scripts/fix_heuristics.py
  - tools/scripts/quality_gate.py
  - tools/scripts/rules_engine/_ast_walkers.py
  - ... 等共 22 个文件

---

## 更新记录: 2026-09-17 20:12:25

### 任务
Git 变更同步

### 变更摘要
- 变更文件 22 个 (+605 / -191 行)
  - .jcode/scripts/governance-auditor.py
  - CHANGELOG.md
  - CONTEXT.md
  - ROADMAP.md
  - docs/adr/ADR-054-phase-34-dedup-common.md
  - docs/adr/ADR-056-phase-36-complexity-gate.md
  - docs/adr/ADR.md
  - pyproject.toml
  - tests/conftest.py
  - tests/test_adg_bootstrap_unit.py
  - tests/test_check_directory_skipped.py
  - tests/test_language_rules_v2.py
  - tests/test_quality_gate_full.py
  - tests/test_rule_registry.py
  - tests/test_semantic_rules.py
  - tests/test_supply_chain_round2.py
  - tools/scripts/_sc_scanners.py
  - tools/scripts/fix_heuristics.py
  - tools/scripts/quality_gate.py
  - tools/scripts/rules_engine/_ast_walkers.py
  - ... 等共 22 个文件

---

## 更新记录: 2026-09-17 20:12:25

### 任务
Git 变更同步

### 变更摘要
- 变更文件 22 个 (+573 / -146 行)
  - .jcode/scripts/governance-auditor.py
  - CHANGELOG.md
  - CONTEXT.md
  - ROADMAP.md
  - docs/adr/ADR-054-phase-34-dedup-common.md
  - docs/adr/ADR-056-phase-36-complexity-gate.md
  - docs/adr/ADR.md
  - pyproject.toml
  - tests/conftest.py
  - tests/test_adg_bootstrap_unit.py
  - tests/test_check_directory_skipped.py
  - tests/test_language_rules_v2.py
  - tests/test_quality_gate_full.py
  - tests/test_rule_registry.py
  - tests/test_semantic_rules.py
  - tests/test_supply_chain_round2.py
  - tools/scripts/_sc_scanners.py
  - tools/scripts/fix_heuristics.py
  - tools/scripts/quality_gate.py
  - tools/scripts/rules_engine/_ast_walkers.py
  - ... 等共 22 个文件

---

## 更新记录: 2026-09-17 12:00:00

### 任务
Phase 36 收口 (cc 门禁落地 + 18 个 ≥10cc 函数拆分) + 文档同步

### 变更摘要
- **Phase 36a**: adg cc 门禁 `check --complexity` + test_adg_cc_gate (6 测试锁定)
- **Phase 36b (7 函数)**: fix_heuristics / jcode_cli / update_ai_tool_matrix / plugins / adg_cli check_file / checker check_file / dependency_graph _run_tarjan_scc
- **Phase 36c (11 函数)**: _shared / loader / basic_checks / domain_checks ×2 / link_auditor / rule_marketplace / auto_fix / pattern_learner / quality_trends / rule_docs_mapper 全部拆至模块级 helper
- **adg check tools/scripts --complexity**: 18 → **0 errors**（全目录 cc≤10 收敛）
- 全量 pytest: **4006 passed, 1 failed**（仅 test_skips_skipped_results 预存 / ADR-053）
- 相关模块 523 tests + mypy strict + ruff 全过
- ADR-056 新增（累计 56 条）+ ADR.md 索引同步 (050-056)

### 当前状态
- master HEAD: `d0ad2c5` (前置, Phase 34c-f/33b 已提交)
- 工作区: 大量待提交改动（Phase 34-36 全部 + 文档）
- 累计: 56 ADR / 4006 tests / tools/scripts cc 全目录 0 error
- 待办: git commit 授权（用户确认后提交）

---

## 更新记录: 2026-09-04 01:12:21

### 任务
Git 变更同步

### 变更摘要
- 变更文件 6 个 (+229 / -129 行)
  - ADR.md
  - CONTEXT.md
  - docs/adr/ADR-038-optimization-scan.md
  - tools/scripts/_common.py
  - tools/scripts/generate_fixes.py
  - tools/scripts/validate_rule_tests.py

---

## 更新记录: 2026-09-04 01:12:20

### 任务
Git 变更同步

### 变更摘要
- 变更文件 6 个 (+213 / -116 行)
  - ADR.md
  - CONTEXT.md
  - docs/adr/ADR-038-optimization-scan.md
  - tools/scripts/_common.py
  - tools/scripts/generate_fixes.py
  - tools/scripts/validate_rule_tests.py

---

## 更新记录: 2026-09-04 01:12:19

### 任务
Git 变更同步

### 变更摘要
- 变更文件 6 个 (+198 / -103 行)
  - ADR.md
  - CONTEXT.md
  - docs/adr/ADR-038-optimization-scan.md
  - tools/scripts/_common.py
  - tools/scripts/generate_fixes.py
  - tools/scripts/validate_rule_tests.py

---

## 更新记录: 2026-09-03 20:59:19

### 任务
Git 变更同步

### 变更摘要
- 变更文件 3 个 (+157 / -0 行)
  - ADR.md
  - CONTEXT.md
  - docs/adr/ADR-038-optimization-scan.md

---

## 更新记录: 2026-09-03 10:49:29

### 任务
Git 变更同步

### 变更摘要
- 变更文件 9 个 (+495 / -273 行)
  - ADR.md
  - CHANGELOG.md
  - CONTEXT.md
  - ROADMAP.md
  - docs/adr/ADR-035-public-api-actual-mapping.md
  - pyproject.toml
  - tests/test_rule_loader_public_api.py
  - tests/test_rule_loader_yaml_merge.py
  - tools/scripts/rules_engine/rule_loader.py

---

## 更新记录: 2026-09-03 10:49:28

### 任务
Git 变更同步

### 变更摘要
- 变更文件 9 个 (+475 / -22 行)
  - ADR.md
  - CHANGELOG.md
  - CONTEXT.md
  - ROADMAP.md
  - docs/adr/ADR-035-public-api-actual-mapping.md
  - pyproject.toml
  - tests/test_rule_loader_public_api.py
  - tests/test_rule_loader_yaml_merge.py
  - tools/scripts/rules_engine/rule_loader.py

---

## 更新记录: 2026-09-04 01:11:00

### 任务
Phase 33a-1 (semantic_checker 纯函数) + Phase 34 (_discover_languages 抽取)

### 变更摘要
- **Phase 33a-1**: tests/test_semantic_checker_pure.py (155 行, 12 测试)
  - _check_from_import / _check_module_import / ImportGraph.add_edge 全覆盖
  - 12/12 passed in 1.19s
- **Phase 34**: 抽 _discover_languages → _common.py::discover_languages
  - 2 处 100% 相同 → 1 个公共函数 + 2 个 back-compat shim
  - ruff --fix 自动修排序
- **测试套件**: 3703 → 3715 (+12 semantic_checker)
- ADR-039 + ADR.md 索引更新
- ADR 累计 40 条

### 当前状态
- master HEAD: `bdd3b83` (前置)
- 工作区: 待提交
- 累计: 40 ADR / 17 降级规则 / 3715 tests

---

## 更新记录: 2026-09-03 19:08:00

### 任务
全面扫描项目可优化内容 (非"找 bug", 而"找优化点")

### 变更摘要
- **ADR-038 全面扫描报告**:
 - 4 个大文件 (>1k 行, 拆分候选): language_registry 1898 / supply_chain 1190 / ast_parser 1148
 - 7 个高 cc 函数 (≥10, 重构候选)
 - **72 组重复私有函数** (同名跨文件, 最高 ROI)
 - 8 个 TODO/FIXME 文件
 - 5680 info adg 误报
- 4 个后续 Phase 规划 (Phase 34-38, 估时 5-9 天)
- Phase 34 优先 (重复函数抽取)

### 当前状态
- master HEAD: `171b75c` (前置)
- 工作区: clean
- 累计: 38 ADR / 17 降级规则 / 3771 tests

---

## 更新记录: 2026-09-03 15:11:00

### 任务
B 深度二次分析 + setup.cfg 配置冲突修复

### 变更摘要
- **真实发现 (ADR-037)**: setup.cfg 与 pyproject.toml mutmut 配置冲突
  - `source_paths` (mutmut 1.x) vs `paths_to_mutate` (mutmut 2.x)
  - setup.cfg runner 引用 2 个不存在的测试文件
- 删除 setup.cfg, 单一 pyproject.toml 配置源
- 实测 mutmut run 跑通 (demo)
- 无 .bak 残留

### 当前状态
- master HEAD: `0715d29` (前置)
- 工作区: clean
- 累计: 37 ADR / 17 降级规则 / 3771 tests

---

## 更新记录: 2026-09-03 10:40:00

### 任务
全面状态分析 + 文档同步 (CHANGELOG / pyproject / ROADMAP)

### 变更摘要
- **CHANGELOG v2.23.5**: Phase 32 完整收口节点 (5 子任务 + ADR-031~035)
- **pyproject version**: 2.23.4 → **2.23.5** (与 CHANGELOG 对齐)
- **ROADMAP**: Phase 32 标 ✅ 完成 (regex_cache 100% + rule_loader 81.28%)
- **CONTEXT**: 63 → 50 条 (第七次主动收敛)
- 剩余: semantic_checker / semantic_rules (标 Phase 33 下次会话)

### 当前状态
- master HEAD: `c06ae70` (前置)
- 工作区: clean (除待提交)
- 累计: 35 ADR / 17 降级规则 / 3771 tests / 86.67% 覆盖率
- **Phase 32 完整收口** ✅

---

## 更新记录: 2026-09-03 08:43:00

### 任务
处理所有已规划但未实施的任务 (Phase 33 refactor + pytest.ini 简化 + Phase 32 子任务 2e)

### 变更摘要
- **Phase 33 refactor** (ADR-034): `_merge_anti_patterns(base, [])` 返回 `list(base)` 副本 (不共享引用)
- **pytest.ini 简化**: 删除 pyproject.toml 重复 pytest 配置,消除 WARNING
- **Phase 32 子任务 2e 公开 API 覆盖** (ADR-035):
 - `load_rules` 6 测试 (cache hit/miss/disk cache/generated/etc)
 - `load_custom_rules` 3 测试 (3 源合并)
 - `load_rules_for_language` 2 测试 (别名)
 - `load_domain_rules` 3 测试 (config + 加载 + 兜底)
 - `_load_generated_rules` + `_load_common_rules` + `_load_universal_rules` 内部 helper
- **覆盖率突破**: rule_loader.py 51% → **81.28%** (跨过 80% 门禁)
- 测试套件: 3748 → **3771** (+23)
- 修复 1 个真实低风险 bug (共享引用)

### 当前状态
- master HEAD: `a5145a4` (前置)
- 工作区: clean (除待提交)
- 累计: 35 ADR / 17 降级规则 / 3771 tests / **rule_loader.py 81.28%** / 总 86.67%
- **Phase 32 完整收口** (5/5 子任务全部完成) ✅

---

## 更新记录: 2026-09-03 08:34:00

### 任务
session 收尾: mypy 警告注释 + CONTEXT 收敛

### 变更摘要
- **pyproject.toml 注释** (3 行): 说明 pygls overrides 段的 mypy 警告来源
 (pygls 是可选依赖, 未安装时 mypy 报 unused section, 但删了会引入 mypy 错误)
- **CONTEXT 主动收敛**: 60+ → 50 条
- 主动停止: session 拒绝"自动"启动 2e (避免延伸)

### 当前状态
- master HEAD: `39bd7ad` (前置)
- 工作区: clean (除待提交)
- 累计: 34 ADR / 17 降级规则 / 3748 tests / rule_loader.py 51% 覆盖

---

## 更新记录: 2026-09-03 01:45:00

### 任务
Phase 32 子任务 2d yaml/merge 覆盖 + ADR-034

### 变更摘要
- **tests/test_rule_loader_yaml_merge.py** (333 行, 23 测试)
  - _load_common_rules_cached (5 分支)
  - _load_universal_rules_cached (4 分支)
  - _try_load_yaml (3 分支)
  - _merge_rules (6 分支)
  - _merge_anti_patterns (5 分支)
- **真实发现 (ADR-034)**: `_merge_anti_patterns(base, [])` 返回 base 本身
  (共享引用, 低风险, 待 refactor)
- 覆盖率: rule_loader.py 24% → **51%** (+27pp, 重大进展)
- 测试套件: 3725 → **3748** (+23)

### 当前状态
- master HEAD: `a580fd9` (前置)
- 工作区: clean
- 累计: 34 ADR / 17 降级规则 / 3748 tests

---

## 更新记录: 2026-09-03 00:50:00

### 任务
Phase 32 子任务 2c rules_hash 覆盖 + ADR-033

### 变更摘要
- **tests/test_rule_loader_rules_hash.py** (164 行, 8 测试)
  - _rules_hash_cached 6 分支 (多文件/缺失/单文件/OSError/LRU hit/LRU miss)
  - _rules_hash 2 分支 (默认 + 显式 framework_dir)
- **ADR-033**: mock 设计 + **关键 Python 陷阱** (from X import Y 形成绑定, mock 模块属性而非导入路径)
- 覆盖率: rule_loader.py 18% → **24%** (+6pp)
- 测试套件: 3717 → **3725** (+8)

### 当前状态
- master HEAD: `0c30292` (前置)
- 工作区: clean
- 累计: 33 ADR / 17 降级规则 / 3725 tests

---

## 更新记录: 2026-09-02 23:53:00

### 任务
Phase 32 子任务 2b disk_cache 覆盖 + ADR-032

### 变更摘要
- **tests/test_rule_loader_disk_cache.py** (129 行, 8 测试)
  - _load_disk_cache 5 分支 (无文件/合法 JSON/JSONDecodeError/空文件/OSError)
  - _save_disk_cache 3 分支 (mkdir+write/覆盖/OSError 兜底)
- **ADR-032**: mock 设计决策 (monkeypatch 模块级常量)
- 覆盖率: rule_loader.py 14% → **18%** (+4pp)
- 测试套件: 3709 → **3717** (+8)

### 当前状态
- master HEAD: `a34cf5d` (前置)
- 工作区: clean
- 累计: 32 ADR / 17 降级规则 / 3717 tests

---

## 更新记录: 2026-09-02 20:12:00

### 任务
session 收尾: CONTEXT 收敛 + ADR-030 Phase 32 启动规划

### 变更摘要
- CONTEXT 57 → 50 条 (第五次主动收敛)
- **ADR-030**: Phase 32 启动规划 (子任务分解, 不实施)
  - 2a `_file_hash` (5 min)
  - 2b `_disk_cache` 系列 (1h)
  - 2c `_rules_hash_cached` (1h)
  - 2d yaml 加载 (2h)
  - 2e 公开 API + 缓存失效 (2h)
- 主动停止: 本轮只做规划, 不实施任何测试

### 当前状态
- master HEAD: `7cf38c1` (前置)
- 工作区: clean
- 累计: 29 ADR / 17 降级规则 / 3703 tests / 86.67% 覆盖率

---

## 更新记录: 2026-09-02 16:38:00

### 任务
后续开发规划 + ADR-029 Phase 32 规划

### 变更摘要
- **优化后计划**: Phase 32 (rule_loader) / Phase 33 (semantic_*) / Phase 34 (集成测试) / Phase 35 (例行维护)
- **ADR-029**: Phase 32 rule_loader.py 覆盖率补测规划 (274 行, 4-6h 工作量, session 已饱和)
  - 列未覆盖分支清单 + 推荐测试结构
  - 预期: rule_loader 77% → 95%+, 总 86.67% → 88%+
- **ROADMAP 更新**: regex_cache ✅ 标记完成 + rule_loader 标 Phase 32 起点
- **主动停止**: 不在本会话实施 rule_loader (大工程风险高于价值)
- CONTEXT 56 → 50 条

### 当前状态
- master HEAD: `8b66ffc` (前置)
- 工作区: clean (除待提交)
- 累计: 29 ADR / 17 降级规则 / 0 error / 0 warning / 3703 tests / regex_cache 100%

---

## 更新记录: 2026-09-02 03:58:00

### 任务
Git 变更同步

### 变更摘要
- 变更文件 6 个 (+233 / -61 行)
  - .jcode/hooks.json
  - ADR.md
  - CHANGELOG.md
  - CONTEXT.md
  - docs/adr/ADR-026-phase-30-hooks-json-integrity.md
  - tools/scripts/check_hooks_json_integrity.sh

---

## 更新记录: 2026-09-02 03:57:50

### 任务
Git 变更同步

### 变更摘要
- 变更文件 6 个 (+217 / -46 行)
  - .jcode/hooks.json
  - ADR.md
  - CHANGELOG.md
  - CONTEXT.md
  - docs/adr/ADR-026-phase-30-hooks-json-integrity.md
  - tools/scripts/check_hooks_json_integrity.sh

---

## 更新记录: 2026-09-02 03:57:49

### 任务
Git 变更同步

### 变更摘要
- 变更文件 6 个 (+200 / -0 行)
  - .jcode/hooks.json
  - ADR.md
  - CHANGELOG.md
  - CONTEXT.md
  - docs/adr/ADR-026-phase-30-hooks-json-integrity.md
  - tools/scripts/check_hooks_json_integrity.sh

---

## 更新记录: 2026-09-02 08:15:00

### 任务
pyproject version 同步 CHANGELOG (2.23.0 → 2.23.3)

### 变更摘要
- **pyproject.toml version 校正**: 2.23.0 → 2.23.3 (CHANGELOG 已发 3 个节点)
- ROADMAP 治理指标 460 → 509 (前轮)
- CHANGELOG v2.23.3 节点已对齐版本号

### 当前状态
- master HEAD: `fade523` (前置)
- 工作区: clean (除 pyproject.toml)
- 累计: 26 ADR / 17 降级规则 / 0 error / 0 warning / 3683 tests
- pyproject version: 2.23.3 ✅ 与 CHANGELOG 对齐

---

## 更新记录: 2026-09-02 15:43:00

### 任务
session 收尾: CONTEXT 收敛 + ROADMAP Phase 31 状态更新

### 变更摘要
- CONTEXT 54 → 50 条 (主动维护)
- ROADMAP Phase 31 状态: ai-tool-matrix ✅ + 覆盖率(regex_cache 100%) ✅
- 主动停止再加新特性 (session 已 27 commit + 28 ADR)
- 剩余 3 个 <80% 模块 (rule_loader/semantic_checker/semantic_rules) 标 Phase 31+ 后续

### 当前状态
- master HEAD: `f335133` (前置)
- 工作区: clean
- 累计: 28 ADR / 17 降级规则 / 0 error / 0 warning / 3703 tests

---

<!-- 滚动窗口: 已自动裁剪 1 条旧更新记录 -->
