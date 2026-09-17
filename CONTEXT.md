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

## 更新记录: 2026-09-02 15:43:00

### 任务
session 收尾: CONTEXT 收敛 + ROADMAP Phase 31 状态更新

### 变更摘要
- CONTEXT 主动收敛 (本轮 54 → 50)
- ROADMAP Phase 31 状态: ai-tool-matrix ✅ + 覆盖率(regex_cache 100%) ✅
- 主动停止再加新特性 (session 已 28 commit + 28 ADR)
- 剩余 3 个 <80% 模块 (rule_loader/semantic_checker/semantic_rules) 标 Phase 31+ 后续

### 当前状态
- master HEAD: `f335133` (前置)
- 工作区: clean
- 累计: 28 ADR / 17 降级规则 / 0 error / 0 warning / 3703 tests / regex_cache 100%

---

## 更新记录: 2026-09-02 14:19:00

### 任务
session 收尾: CONTEXT 收敛 + 健康确认

### 变更摘要
- CONTEXT 53 → 50 条 (实测文档步骤第二次)
- session 主动判断:不再加新特性 (已 21 commit + 27 ADR)
- 剩余 4 个 <80% 覆盖率模块 (Phase 31+ 大工程, 本会话不实施)
- 健康检查全过: ruff / adg error / check_rules_yml / check_hooks_json

### 当前状态
- master HEAD: `ba9ff84` (前置)
- 工作区: clean
- 累计: 27 ADR / 17 降级规则 / 0 error / 0 warning / 3683 tests / 86.67% 覆盖率
- session 已完整闭环, 主动停止再加新特性

---

## 更新记录: 2026-09-02 13:23:00

### 任务
按文档步骤实测 CONTEXT 收敛 + 验证

### 变更摘要
- CONTEXT 52 → 50 条 (实测文档步骤)
- 关键决策块 (11:50 / 08:15 / 03:36 / 03:05 / 21:50 等) 全部保留
- CONTEXT.md 1029 行 (1075 → 1029, -46 行)

### 当前状态
- master HEAD: `32671b5` (前置)
- 工作区: clean
- 累计: 27 ADR / 17 降级规则 / 0 error / 0 warning / 3683 tests

---

## 更新记录: 2026-09-02 11:50:00

### 任务
按建议实施 P0/P1/P2 + Phase 30 双层防护首次主动拦截

### 变更摘要
- **P0 CONTEXT 维护文档** (docs/governance/context-maintenance.md): 50 条滚动窗口维护步骤
- **P1 mutmut CI 化** (tools/scripts/mutmut_ci.sh):
  - 三模式: 全量 / --changed-only / --files F1 F2
  - 5 分钟超时, 主动清理 .bak + .mutmut-cache
  - 接入 on_pr 条件触发 (Python 文件改动时跑)
- **Phase 30 双层防护首次主动拦截** (ADR-027):
  - session 内 .adg/rules.yml severity_overrides 段被覆写丢失
  - check_rules_yml_integrity.sh 立即捕获 + 退出 1
  - git checkout HEAD -- .adg/rules.yml 恢复成功
  - 真实事件验证 ADR-025 设计有效
- **P2 覆盖率实测**: 3683 passed in 18m18s, 86.67% (门禁 80%, +6.67%)
  - 4 个 <80% 模块: regex_cache 78% / rule_loader 77% / semantic_checker 73% / semantic_rules 72%
  - 标记为大工程待 Phase 31+ (未实施)
- 新增 ADR-027
- ROADMAP Phase 31 标记 mutmut CI 化 ✅ + 双层防护首次拦截 ✅
- CHANGELOG v2.23.4 节点
- pyproject version 2.23.3 → 2.23.4

### 当前状态
- master HEAD: `68de517` (前置, CONTEXT 文档提交)
- 工作区: clean (除待提交)
- 累计: 27 ADR / 17 降级规则 / 0 error / 0 warning / 3683 tests / 86.67% 覆盖率
- on_commit 6/6 ✅ / on_merge 3/3 ✅ / on_pr 11 (含新 mutmut-changed)

---

## 更新记录: 2026-09-02 03:36:00

### 任务
Phase 30 收口: hooks.json fail-open 检测脚本 + ADR-026

### 变更摘要
- **新增 `tools/scripts/check_hooks_json_integrity.sh`** (1647 字节, +x)
  - 通过真跑 hooks_runner 检测 hook 命令参数不支持
  - 比 --bogus-arg 探针更准确(实测发现探针会把所有 argparse 脚本误判)
- **`.jcode/hooks.json` on_commit 新增 `hooks-json-integrity-check`**
  - 条件触发 `files_contain('.jcode/hooks.json')`
  - 改 hooks.json 时自动验证 fail-open 风险
- **正向触发验证**: on_commit 真跑 6/6 通过 (含新增)
- **反向测试验证**: 注入 link_auditor.py --update-moc 类 hook 立即被脚本捕获
- 新增 **ADR-026** 记录决策链
- CHANGELOG v2.23.3 节点
- on_commit 现 6 hooks

### 当前状态
- master HEAD: `52b5c64` (前置)
- 工作区: clean
- 累计: 26 ADR / 17 降级规则 / 0 error / 0 warning / 3683 tests
- on_commit 6/6 ✅ / on_merge 3/3 ✅

---

## 更新记录: 2026-09-02 03:05:00

### 任务
Phase 30 落地 + update-moc bug 修复 + on_merge 全验证通过

### 变更摘要
- **on_merge 新增 `rules-yml-integrity-check-merge` hook** (Phase 30 双层防护)
- **正向触发验证**: `hooks_runner on_merge` 真触发新 hook 并通过 ✅
- **移除 fail-open `update-moc` hook** (方案 A): link_auditor.py 是只读审计器,从未实现 `--update-moc`。方案 A 落地: 从 hooks.json 移除该 hook, MOC 人工维护
- **on_merge 全验证**: 3 个 hook (sync-tools / context-sync-merge / rules-yml-integrity-check-merge) 全过 ✅
- 新增 **ADR-025** 决策 4 记录方案 A 落地
- ADR.md 索引补 ADR-025
- ROADMAP Phase 31 标记 update-moc 已落地
- CHANGELOG v2.23.2 节点

### 当前状态
- master HEAD: `eb41676` (前置)
- 工作区: clean
- 累计: 25 ADR / 17 降级规则 / 0 error / 0 warning / 3683 tests
- on_merge 全过 ✅ / on_commit 5/5 ✅

---

## 更新记录: 2026-09-01 22:14:31

### 任务
Git 变更同步

### 变更摘要
- 变更文件 1 个 (+28 / -0 行)
  - CONTEXT.md

---

## 更新记录: 2026-09-01 21:50:00

### 任务
收口 + 校正 + 严谨化 (诚实修正前轮过度声称)

### 校正
- **真实反向门禁复测**: 删除 `py-ci-disabled-check` + `py-file-leak` 两条后, check_rules_yml_integrity.sh 立即报错并退出 1, 恢复后通过 ✅ (非 mtime 改动而是真删内容)
- **CONTEXT.md 体量**: 1085 行 / 55 条更新记录 (设计上限 50 条, 略超)
- **pytest 真实全量**: 3683 passed in 318.08s (非 42 个抽样)

### 本会话累计 commit (8 个, 全部 push-ready)
398740a docs(changelog/roadmap): Phase 29 完整收口 + 验证快照
3ba06a7 feat(phase-29): mutmut 配置修正 + 单文件 demo 基线 (ADR-024)
23be19d docs(context): HEAD 校正 + 澄清 context-sync 与人工维护无冲突
632406a docs(context): 校正 HEAD 引用 9959dc8 → f1ed5e9 + 二次复跑证据
f1ed5e9 docs(context): 补强端到端验证证据 (实跑, 非检查)
1f9f39d docs(context): 记录 Phase 29 P1 实施完成
9959dc8 feat(phase-29): py-file-leak 17 类降级 + 修 1 真问题 + hooks 集成
1d7a07d chore(phase-28): check_rules_yml_integrity.sh 上线 + CHANGELOG v2.23.1

### 当前状态
- master HEAD: `398740a`
- 工作区: clean
- 累计: 24 ADR / 17 降级规则 / 0 error / 0 warning / 3683 tests / 192 源文件 mypy strict Success
- 工具链: ruff ✅ / adg ✅ / mypy strict ✅ / pytest ✅ / mutmut ✅ / hooks ✅

---

## 更新记录: 2026-09-01 21:07:30

### 任务
补强验证 + 端到端测试 + 反向门禁测试

### 端到端验证证据 (实跑,非检查)
- **pytest 42 个 validate_case_study 测试** ✅ 9.40s 全过 (验证 9959dc8 改动未破坏)
- **hooks_runner on_commit 端到端** ✅ 真触发 `rules-yml-integrity-check` 并通过
- **反向门禁测试** ✅ 删除 `common-empty-except-block` 关键规则后 hook 链退出码 1, 阻断提交; 恢复后通过
- **反向脚本测试** ✅ 删除 `py-file-leak` 关键规则后 `check_rules_yml_integrity.sh` 立即报错
- **mypy strict 抽查** ✅ `lsp_server.py` / `validate_case_study.py` / `exception_manager.py` 均 Success
- **validate_case_study.py --all** ✅ 真实跑全量案例验证 (改动行触发), All checks passed
- **pytest collect** ✅ 3683 tests collected (与历史快照一致)

### 当前状态
- master HEAD: `632406a` (HEAD 校正 + 二次复跑)
- 工作区: clean
- 累计: 23 ADR / 17 降级规则 / 0 error / 0 warning
- 真实验证 (二次复跑, 2026-09-01 21:09): pytest 42 passed in 3.58s, adg error/warning 0/0, check_rules_yml_integrity 18 规则完整
- context-sync 实测: 人工撰写的"补强验证"块被正确识别为更新记录,不会被 hook 覆盖; 仅裁剪 > 50 条的旧记录 (设计如此, 非冲突)

---

## 更新记录: 2026-09-01 20:55:00

### 任务
Phase 29 P1 实施 - py-file-leak 治理 + 完整性脚本 v1.1 + hooks 集成

### 变更摘要
- **py-file-leak 12 个命中分析** - 11 个 with 块误报 + 1 个 urllib 误判, 仅 1 个真实问题 (`validate_case_study.py:685 open(filepath).read()`)
- **修复 1 个真实问题** - `validate_case_study.py:685` 改为 `Path(filepath).read_text(encoding="utf-8")` (Pythonic 风格)
- **`py-file-leak` 降级 info** - `.adg/rules.yml` + `pyproject.toml` 同步, 注释含分析理由
- **`check_rules_yml_integrity.sh` v1.1 升级** - 从"行数比对"改为"17 类关键规则 key 校验", 避免合法新增触发误报 (本次会话即触发一次)
- **`.jcode/hooks.json` 集成 `rules-yml-integrity-check`** - on_commit + 条件 `files_contain('.adg/rules.yml')`, 改规则文件时自动校验
- **新增 ADR-023** 记录 Phase 29 py-file-leak 决策链 + 累计 17 类降级规则
- **ROADMAP Phase 29 P1 完成** - 剩余 3 项候选 (common-empty-except-block 收尾/mypy strict/mutmut)

### common-empty-except-block 抽样验证
- 30 个分布在 26 个文件, ADR-022 已决策保留 info
- 抽样 3 个: `exception_manager.py:756` (except ValueError: pass, ISO 格式容错) / `checker.py:441` (except Exception + debug 注释) / `context_status.py:36` (except OSError: pass, 容错读 pyproject)
- 全部为合理 best-effort 模式, 无需进一步修复

### 验证
- ruff check: clean
- adg check (error): 0 issues / 192 files
- adg check (warning): 0 issues / 192 files
- adg check (info): 5680 issues / 192 files (-1 来自修真实问题)
- check_rules_yml_integrity.sh: ✅ 18 个降级规则完整
- hooks.json JSON 合法性: OK

### 当前状态
- master HEAD: `9959dc8` (Phase 29 P1)
- 工作区: clean
- 累计: 23 ADR / 17 降级规则 / 0 error / 0 warning

---

## 更新记录: 2026-09-01 20:34:00

### 任务
Phase 28 收口 + check_rules_yml_integrity.sh 提交 + Phase 29 规划

### 变更摘要
- **新增 `tools/scripts/check_rules_yml_integrity.sh`** (1667 字节, +x)
  - 行数比对 HEAD vs 工作区 `.adg/rules.yml`
  - 不匹配立即报错 + 提示 `git checkout HEAD -- .adg/rules.yml` 恢复
  - 解决 Phase 28 内两次发生 `severity_overrides` 段 (65 行) 工作区丢失事件
- **修复脚本可执行权限** - chmod +x
- **CHANGELOG 补 v2.23.1 节点** - 记录本次 Phase 28 收口
- **ROADMAP 增量**:
  - 新增"Phase 28 收口 (2026-09-01)"块
  - 基于实测数据修正 py-file-leak 15→12 / common-empty-except-block 34→30
  - Phase 29 候选重新定义为 5 项 (含 hooks 集成 check_rules_yml_integrity.sh)

### 验证
- ruff check: clean
- adg check (error): 0 issues / 192 files
- adg check (warning): 0 issues / 192 files
- adg check (info): 5681 issues / 192 files
- check_rules_yml_integrity.sh: ✅ .adg/rules.yml 完整 (127 行)

### 当前状态
- master HEAD: `2dc98da` (未变更)
- 工作区: 1 untracked + 2 modified
  - `tools/scripts/check_rules_yml_integrity.sh` (new, +x)
  - `CHANGELOG.md` (modified) - v2.23.1 节点
  - `ROADMAP.md` (modified) - Phase 28 收口 + Phase 29 重新定义
- 待规划: Phase 29 实施 (5 个候选)

---

## 更新记录: 2026-08-31 22:35:00

### 任务
Phase 28 收尾修复 + 空 except 治理 + 后续规划

### 变更摘要
- 修复 3 处问题
  - **ADR.md 索引补齐** - 14 → 23 行, 新增 ADR-013~022 共 10 条
  - **`.adg/rules.yml` 恢复** - 工作区丢失的 65 行 `severity_overrides` 段被 `git checkout HEAD --` 恢复
  - **`py-ci-disabled-check` 降级为 info** - 4 个 warning → 0
- 启动 Phase 28 P1: 空 except 治理
  - 3 处 `except Exception` 收窄为 `except OSError`
    - `rules_engine/arch/dependency_graph.py:122`
    - `rules_engine/pattern_learner.py:115`
    - `rules_engine/pattern_learner.py:169`
  - 34 个剩余 `common-empty-except-block` 决策保留 info (详见 ADR-022)
- 新增 ADR-022 记录 Phase 28 启动 + 治理原则
- pyproject.toml `severity_overrides` 同步至 15 类 (新增 py-ci-disabled-check)
- ROADMAP 标记 Phase 28 完成 + 新增 Phase 29 候选 (mypy strict / mutmut / py-file-leak)

### 验证
- ruff check: clean
- pytest: 3683 passed in 441.76s (0:07:21)
- adg check (error): 0 issues / 205 files
- adg check (warning): **0 issues / 205 files** (从 4 → 0)
- adg check (info): 5878 issues / 205 files

### 当前状态
- master HEAD: `ddc08af` (未变更, 工作区有 5 文件待提交)
- 工作区: 3 files modified + 2 files added
  - `ADR.md` (modified) - 索引补齐
  - `ROADMAP.md` (modified) - Phase 28 完成
  - `.adg/rules.yml` (modified) - 恢复 + py-ci-disabled-check
  - `pyproject.toml` (modified) - severity_overrides 同步
  - `docs/adr/ADR-022-...md` (new) - Phase 28 ADR
- 待规划: Phase 29 方向 (mypy strict / mutmut / py-file-leak)

---

## 更新记录: 2026-08-31 06:11:00

### 任务
项目清理与状态收口（会后扫尾）

### 变更摘要
- 提交 2 个 fix commit
  - `1728264` fix(quality): 清理 ruff 错误 + gitignore 漏洞 + 陈旧 baseline 豁免
    - `tools/scripts/audit_attestation.py` 删 F841 未使用变量 `prev_hash`
    - `tools/scripts/rule_catalog.py` UP035 改 `Iterator` 从 `collections.abc` 导入
    - `.gitignore` 补 `.coverage-v*.json` 模式
    - `.jcode/baseline.json` 删 `tools/scripts/rules/loader.py` 53 行陈旧豁免
  - `7f1f1e5` chore(gitignore): 忽略 `tools/.quality-trends/audit_ledger.jsonl`
- 删除 2 个本地/远端遗留分支（master 已领先 458+ commits，已被吸收）
  - `feat/ci-validation-test` (master 领先 459)
  - `test/diff-cover-test` (master 领先 458)

### 验证
- ruff check: clean
- pytest: 3683 passed in 474.80s (0:07:54)
- adg check (error 级): 0 issues / 192 files
- adg check (warning 级): 1236 py-log-print + 1 common-empty-except-block（属历史软警告，非阻塞）

### 当前状态
- master HEAD: `7f1f1e5`
- 工作区 clean
- 待规划: Phase 25 方向（质量巩固 / 功能增强 / 文档升级）

---

## 更新记录: 2026-08-29 09:58:47

### 任务
Git 变更同步

### 变更摘要
- 变更文件 13 个 (+722 / -77 行)
  - .adg/config.yml
  - .gitignore
  - CHANGELOG.md
  - CONTEXT.md
  - docs/adr/ADR-013-pytest-xdist-coverage-known-issue.md
  - docs/adr/ADR.md
  - docs/governance/project-analysis-and-roadmap-2026-08.md
  - pyproject.toml
  - tests/test_lsp_server.py
  - tests/test_p1_2_auto_fix_dispatch.py
  - tools/scripts/adg_cli/commands/cmd/cmd_fix.py
  - tools/scripts/auto_fix.py
  - uv.lock

---

## 更新记录: 2026-08-29 09:03:10

### 任务
Git 变更同步

### 变更摘要
- 变更文件 13 个 (+699 / -61 行)
  - .adg/config.yml
  - .gitignore
  - CHANGELOG.md
  - CONTEXT.md
  - docs/adr/ADR-013-pytest-xdist-coverage-known-issue.md
  - docs/adr/ADR.md
  - docs/governance/project-analysis-and-roadmap-2026-08.md
  - pyproject.toml
  - tests/test_lsp_server.py
  - tests/test_p1_2_auto_fix_dispatch.py
  - tools/scripts/adg_cli/commands/cmd/cmd_fix.py
  - tools/scripts/auto_fix.py
  - uv.lock

---

## 更新记录: 2026-08-28 23:47:51

### 任务
Git 变更同步

### 变更摘要
- 变更文件 10 个 (+333 / -58 行)
  - .adg/config.yml
  - .gitignore
  - CHANGELOG.md
  - CONTEXT.md
  - docs/adr/ADR-013-pytest-xdist-coverage-known-issue.md
  - docs/adr/ADR.md
  - docs/governance/project-analysis-and-roadmap-2026-08.md
  - pyproject.toml
  - tests/test_lsp_server.py
  - uv.lock

---

## 更新记录: 2026-08-28 23:45:16

### 任务
Git 变更同步

### 变更摘要
- 变更文件 10 个 (+313 / -44 行)
  - .adg/config.yml
  - .gitignore
  - CHANGELOG.md
  - CONTEXT.md
  - docs/adr/ADR-013-pytest-xdist-coverage-known-issue.md
  - docs/adr/ADR.md
  - docs/governance/project-analysis-and-roadmap-2026-08.md
  - pyproject.toml
  - tests/test_lsp_server.py
  - uv.lock

---

## 更新记录: 2026-08-28 23:43:48

### 任务
Git 变更同步

### 变更摘要
- 变更文件 10 个 (+293 / -31 行)
  - .adg/config.yml
  - .gitignore
  - CHANGELOG.md
  - CONTEXT.md
  - docs/adr/ADR-013-pytest-xdist-coverage-known-issue.md
  - docs/adr/ADR.md
  - docs/governance/project-analysis-and-roadmap-2026-08.md
  - pyproject.toml
  - tests/test_lsp_server.py
  - uv.lock

---

## 更新记录: 2026-08-28 19:22:03

### 任务
Git 变更同步

### 变更摘要
- 变更文件 7 个 (+162 / -29 行)
  - ADR.md
  - CHANGELOG.md
  - CONTEXT.md
  - docs/adr/ADR-012-vector-rag-not-core.md
  - docs/governance/project-analysis-and-roadmap-2026-08.md
  - pyproject.toml
  - uv.lock

---

## 更新记录: 2026-08-28 18:42:21

### 任务
Git 变更同步

### 变更摘要
- 变更文件 9 个 (+173 / -48 行)
  - ADR.md
  - CHANGELOG.md
  - CONTEXT.md
  - docs/adr/ADR-012-vector-rag-not-core.md
  - docs/governance/project-analysis-and-roadmap-2026-08.md
  - pyproject.toml
  - tests/test_audit_to_pr.py
  - tests/test_rule_tracker.py
  - uv.lock

---

## 更新记录: 2026-08-28 18:21:47

### 任务
Git 变更同步

### 变更摘要
- 变更文件 8 个 (+152 / -89 行)
  - .github/workflows/release.yml
  - CHANGELOG.md
  - CONTEXT.md
  - docs/governance/project-analysis-and-roadmap-2026-08.md
  - pyproject.toml
  - tests/test_audit_to_pr.py
  - tests/test_rule_tracker.py
  - uv.lock

---

## 更新记录: 2026-08-28 16:47:39

### 任务
Git 变更同步

### 变更摘要
- 变更文件 8 个 (+145 / -78 行)
  - .github/workflows/release.yml
  - .pre-commit-config.yaml
  - CHANGELOG.md
  - CONTEXT.md
  - docs/governance/project-analysis-and-roadmap-2026-08.md
  - mypy.ini
  - pyproject.toml
  - uv.lock

---

## 更新记录: 2026-08-28 15:19:54

### 任务
Git 变更同步

### 变更摘要
- 变更文件 10 个 (+228 / -71 行)
  - .pre-commit-config.yaml
  - CHANGELOG.md
  - CONTEXT.md
  - docs/governance/project-analysis-and-roadmap-2026-08.md
  - mypy.ini
  - pyproject.toml
  - tests/test_adr_generator.py
  - tests/test_ai_context_manager.py
  - tests/test_metrics_telemetry.py
  - uv.lock

---

<!-- 滚动窗口: 已自动裁剪 1 条旧更新记录 -->
