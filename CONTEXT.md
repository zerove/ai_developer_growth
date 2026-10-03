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

## 更新记录: 2026-10-03 19:58:30

### 任务
Git 变更同步

### 变更摘要
- 变更文件 7 个 (+201 / -55 行)
  - CHANGELOG.md
  - CONTEXT.md
  - ROADMAP.md
  - docs/adr/ADR.md
  - docs/api/cli.md
  - tests/test_ast_fixer_write_verification.py
  - tools/scripts/hooks/phase_runner.py

## 更新记录: 2026-10-03 19:51:41

### 任务
Git 变更同步

### 变更摘要
- 变更文件 7 个 (+186 / -42 行)
  - CHANGELOG.md
  - CONTEXT.md
  - ROADMAP.md
  - docs/adr/ADR.md
  - docs/api/cli.md
  - tests/test_ast_fixer_write_verification.py
  - tools/scripts/hooks/phase_runner.py

## 更新记录: 2026-10-03 19:34:54

### 任务
Git 变更同步

### 变更摘要
- 变更文件 6 个 (+442 / -178 行)
  - CHANGELOG.md
  - CONTEXT.md
  - ROADMAP.md
  - docs/adr/ADR-070-verify-syntax-before-writing.md
  - tests/test_rule_docs_mapper_round2.py
  - tools/scripts/rules_engine/rule_docs_mapper.py

## 更新记录: 2026-10-03 19:23:03

### 任务
Git 变更同步

### 变更摘要
- 变更文件 6 个 (+415 / -168 行)
  - CHANGELOG.md
  - CONTEXT.md
  - ROADMAP.md
  - docs/adr/ADR-070-verify-syntax-before-writing.md
  - tests/test_rule_docs_mapper_round2.py
  - tools/scripts/rules_engine/rule_docs_mapper.py

## 更新记录: 2026-10-03 19:07:06

### 任务
Git 变更同步

### 变更摘要
- 变更文件 6 个 (+365 / -155 行)
  - CHANGELOG.md
  - CONTEXT.md
  - ROADMAP.md
  - docs/adr/ADR-070-verify-syntax-before-writing.md
  - tests/test_rule_docs_mapper_round2.py
  - tools/scripts/rules_engine/rule_docs_mapper.py

## 更新记录: 2026-10-03 19:02:46

### 任务
Git 变更同步

### 变更摘要
- 变更文件 10 个 (+560 / -197 行)
  - CHANGELOG.md
  - CONTEXT.md
  - ROADMAP.md
  - docs/adr/ADR-063-tree-sitter-per-language-import.md
  - docs/adr/ADR-064-semantic-degradation-must-be-visible.md
  - docs/adr/ADR-070-verify-syntax-before-writing.md
  - tests/test_ast_parser_partial_install.py
  - tests/test_rule_docs_mapper_round2.py
  - tests/test_semantic_degraded_visibility.py
  - tools/scripts/rules_engine/rule_docs_mapper.py

## 更新记录: 2026-10-03 18:57:41

### 任务
Git 变更同步

### 变更摘要
- 变更文件 10 个 (+542 / -186 行)
  - CHANGELOG.md
  - CONTEXT.md
  - ROADMAP.md
  - docs/adr/ADR-063-tree-sitter-per-language-import.md
  - docs/adr/ADR-064-semantic-degradation-must-be-visible.md
  - docs/adr/ADR-070-verify-syntax-before-writing.md
  - tests/test_ast_parser_partial_install.py
  - tests/test_rule_docs_mapper_round2.py
  - tests/test_semantic_degraded_visibility.py
  - tools/scripts/rules_engine/rule_docs_mapper.py

## 更新记录: 2026-10-03 18:12:07

### 任务
Git 变更同步

### 变更摘要
- 变更文件 11 个 (+500 / -176 行)
  - .jcode/hooks.json
  - CHANGELOG.md
  - CONTEXT.md
  - ROADMAP.md
  - docs/adr/ADR-063-tree-sitter-per-language-import.md
  - docs/adr/ADR-064-semantic-degradation-must-be-visible.md
  - docs/adr/ADR-070-verify-syntax-before-writing.md
  - tests/test_ast_parser_partial_install.py
  - tests/test_rule_docs_mapper_round2.py
  - tests/test_semantic_degraded_visibility.py
  - tools/scripts/rules_engine/rule_docs_mapper.py

## 更新记录: 2026-10-03 18:06:46

### 任务
Git 变更同步

### 变更摘要
- 变更文件 11 个 (+482 / -165 行)
  - .jcode/hooks.json
  - CHANGELOG.md
  - CONTEXT.md
  - ROADMAP.md
  - docs/adr/ADR-063-tree-sitter-per-language-import.md
  - docs/adr/ADR-064-semantic-degradation-must-be-visible.md
  - docs/adr/ADR-070-verify-syntax-before-writing.md
  - tests/test_ast_parser_partial_install.py
  - tests/test_rule_docs_mapper_round2.py
  - tests/test_semantic_degraded_visibility.py
  - tools/scripts/rules_engine/rule_docs_mapper.py

## 更新记录: 2026-10-03 18:00:42

### 任务
Git 变更同步

### 变更摘要
- 变更文件 11 个 (+463 / -154 行)
  - .jcode/hooks.json
  - CHANGELOG.md
  - CONTEXT.md
  - ROADMAP.md
  - docs/adr/ADR-063-tree-sitter-per-language-import.md
  - docs/adr/ADR-064-semantic-degradation-must-be-visible.md
  - docs/adr/ADR-070-verify-syntax-before-writing.md
  - tests/test_ast_parser_partial_install.py
  - tests/test_rule_docs_mapper_round2.py
  - tests/test_semantic_degraded_visibility.py
  - tools/scripts/rules_engine/rule_docs_mapper.py

## 更新记录: 2026-10-03 17:52:57

### 任务
Git 变更同步

### 变更摘要
- 变更文件 11 个 (+443 / -144 行)
  - .jcode/hooks.json
  - CHANGELOG.md
  - CONTEXT.md
  - ROADMAP.md
  - docs/adr/ADR-063-tree-sitter-per-language-import.md
  - docs/adr/ADR-064-semantic-degradation-must-be-visible.md
  - docs/adr/ADR-070-verify-syntax-before-writing.md
  - tests/test_ast_parser_partial_install.py
  - tests/test_rule_docs_mapper_round2.py
  - tests/test_semantic_degraded_visibility.py
  - tools/scripts/rules_engine/rule_docs_mapper.py

## 更新记录: 2026-10-03 17:49:21

### 任务
Git 变更同步

### 变更摘要
- 变更文件 10 个 (+418 / -133 行)
  - CHANGELOG.md
  - CONTEXT.md
  - ROADMAP.md
  - docs/adr/ADR-063-tree-sitter-per-language-import.md
  - docs/adr/ADR-064-semantic-degradation-must-be-visible.md
  - docs/adr/ADR-070-verify-syntax-before-writing.md
  - tests/test_ast_parser_partial_install.py
  - tests/test_rule_docs_mapper_round2.py
  - tests/test_semantic_degraded_visibility.py
  - tools/scripts/rules_engine/rule_docs_mapper.py

## 更新记录: 2026-10-03 17:46:12

### 任务
Git 变更同步

### 变更摘要
- 变更文件 10 个 (+400 / -122 行)
  - CHANGELOG.md
  - CONTEXT.md
  - ROADMAP.md
  - docs/adr/ADR-063-tree-sitter-per-language-import.md
  - docs/adr/ADR-064-semantic-degradation-must-be-visible.md
  - docs/adr/ADR-070-verify-syntax-before-writing.md
  - tests/test_ast_parser_partial_install.py
  - tests/test_rule_docs_mapper_round2.py
  - tests/test_semantic_degraded_visibility.py
  - tools/scripts/rules_engine/rule_docs_mapper.py

## 更新记录: 2026-10-03 17:42:37

### 任务
Git 变更同步

### 变更摘要
- 变更文件 11 个 (+388 / -106 行)
  - .jcode/hooks.json
  - CHANGELOG.md
  - CONTEXT.md
  - ROADMAP.md
  - docs/adr/ADR-063-tree-sitter-per-language-import.md
  - docs/adr/ADR-064-semantic-degradation-must-be-visible.md
  - docs/adr/ADR-070-verify-syntax-before-writing.md
  - tests/test_ast_parser_partial_install.py
  - tests/test_rule_docs_mapper_round2.py
  - tests/test_semantic_degraded_visibility.py
  - tools/scripts/rules_engine/rule_docs_mapper.py

## 更新记录: 2026-10-03 17:38:32

### 任务
Git 变更同步

### 变更摘要
- 变更文件 10 个 (+363 / -89 行)
  - CHANGELOG.md
  - CONTEXT.md
  - ROADMAP.md
  - docs/adr/ADR-063-tree-sitter-per-language-import.md
  - docs/adr/ADR-064-semantic-degradation-must-be-visible.md
  - docs/adr/ADR-070-verify-syntax-before-writing.md
  - tests/test_ast_parser_partial_install.py
  - tests/test_rule_docs_mapper_round2.py
  - tests/test_semantic_degraded_visibility.py
  - tools/scripts/rules_engine/rule_docs_mapper.py

## 更新记录: 2026-10-03 17:16:30

### 任务
Git 变更同步

### 变更摘要
- 变更文件 8 个 (+231 / -64 行)
  - .jcode/hooks.json
  - CHANGELOG.md
  - CONTEXT.md
  - ROADMAP.md
  - docs/adr/ADR-063-tree-sitter-per-language-import.md
  - docs/adr/ADR-064-semantic-degradation-must-be-visible.md
  - tests/test_ast_parser_partial_install.py
  - tests/test_semantic_degraded_visibility.py

## 更新记录: 2026-10-03 17:15:08

### 任务
Git 变更同步

### 变更摘要
- 变更文件 14 个 (+369 / -71 行)
  - CHANGELOG.md
  - CONTEXT.md
  - ROADMAP.md
  - docs/adr/ADR-063-tree-sitter-per-language-import.md
  - docs/adr/ADR-064-semantic-degradation-must-be-visible.md
  - docs/adr/ADR-068-ast-fix-must-separate-found-from-applied.md
  - docs/adr/ADR.md
  - docs/api/cli.md
  - tests/test_ast_fixer_persistence.py
  - tests/test_ast_parser_partial_install.py
  - tests/test_semantic_degraded_visibility.py
  - tools/scripts/hooks/phase_runner.py
  - tools/scripts/rules_engine/ast_fixer.py
  - tools/scripts/rules_engine/ast_nodes.py

## 更新记录: 2026-10-03 17:09:06

### 任务
Git 变更同步

### 变更摘要
- 变更文件 12 个 (+313 / -52 行)
  - CHANGELOG.md
  - CONTEXT.md
  - ROADMAP.md
  - docs/adr/ADR-068-ast-fix-must-separate-found-from-applied.md
  - docs/adr/ADR.md
  - docs/api/cli.md
  - tests/test_ast_fixer_persistence.py
  - tests/test_ast_parser_partial_install.py
  - tests/test_semantic_degraded_visibility.py
  - tools/scripts/hooks/phase_runner.py
  - tools/scripts/rules_engine/ast_fixer.py
  - tools/scripts/rules_engine/ast_nodes.py

## 更新记录: 2026-10-03 16:59:27

### 任务
Git 变更同步

### 变更摘要
- 变更文件 12 个 (+293 / -38 行)
  - CHANGELOG.md
  - CONTEXT.md
  - ROADMAP.md
  - docs/adr/ADR-068-ast-fix-must-separate-found-from-applied.md
  - docs/adr/ADR.md
  - docs/api/cli.md
  - tests/test_ast_fixer_persistence.py
  - tests/test_ast_parser_partial_install.py
  - tests/test_semantic_degraded_visibility.py
  - tools/scripts/hooks/phase_runner.py
  - tools/scripts/rules_engine/ast_fixer.py
  - tools/scripts/rules_engine/ast_nodes.py

## 更新记录: 2026-10-03 14:28:59

### 任务
Git 变更同步

### 变更摘要
- 变更文件 6 个 (+422 / -30 行)
  - CHANGELOG.md
  - ROADMAP.md
  - docs/adr/ADR-069-auto-fix-must-not-break-syntax.md
  - docs/adr/ADR.md
  - tests/test_ast_fixer_inline_body_safety.py
  - tools/scripts/rules_engine/ast_fixer.py

## 更新记录: 2026-10-03 14:06:01

### 任务
Git 变更同步

### 变更摘要
- 变更文件 3 个 (+34 / -64 行)
  - CONTEXT.md
  - docs/adr/ADR-068-ast-fix-must-separate-found-from-applied.md
  - docs/adr/ADR.md

## 更新记录: 2026-10-03 13:55:51

### 任务
Git 变更同步

### 变更摘要
- 变更文件 3 个 (+23 / -34 行)
  - CONTEXT.md
  - docs/adr/ADR.md
  - tests/test_ast_fixer_full.py

## 更新记录: 2026-10-03 13:44:50

### 任务
Git 变更同步

### 变更摘要
- 变更文件 2 个 (+13 / -4 行)
  - docs/adr/ADR.md
  - tests/test_ast_fixer_full.py

## 更新记录: 2026-10-03 13:24:45

### 任务
Git 变更同步

### 变更摘要
- 变更文件 8 个 (+1482 / -125 行)
  - CHANGELOG.md
  - ROADMAP.md
  - docs/adr/ADR-066-ast-fixer-must-persist-fixes.md
  - docs/adr/ADR.md
  - docs/api/cli.md
  - tests/test_ast_fixer_persistence.py
  - tools/scripts/rules_engine/ast_fixer.py
  - uv.lock

## 更新记录: 2026-10-03 13:07:36

### 任务
Git 变更同步

### 变更摘要
- 变更文件 11 个 (+1869 / -284 行)
  - CHANGELOG.md
  - CONTEXT.md
  - ROADMAP.md
  - docs/adr/ADR-064-semantic-degradation-must-be-visible.md
  - docs/adr/ADR-065-missing-path-must-fail.md
  - docs/adr/ADR.md
  - tests/test_phase2_5_integration.py
  - tests/test_phase_runner_missing_path.py
  - tools/scripts/hooks/phase_runner.py
  - tools/scripts/rules_engine/ast_fixer.py
  - uv.lock

## 更新记录: 2026-10-03 12:57:07

### 任务
Git 变更同步

### 变更摘要
- 变更文件 11 个 (+1850 / -254 行)
  - CHANGELOG.md
  - CONTEXT.md
  - ROADMAP.md
  - docs/adr/ADR-064-semantic-degradation-must-be-visible.md
  - docs/adr/ADR-065-missing-path-must-fail.md
  - docs/adr/ADR.md
  - tests/test_phase2_5_integration.py
  - tests/test_phase_runner_missing_path.py
  - tools/scripts/hooks/phase_runner.py
  - tools/scripts/rules_engine/ast_fixer.py
  - uv.lock

## 更新记录: 2026-10-03 12:44:12

### 任务
Git 变更同步

### 变更摘要
- 变更文件 11 个 (+1831 / -224 行)
  - CHANGELOG.md
  - CONTEXT.md
  - ROADMAP.md
  - docs/adr/ADR-064-semantic-degradation-must-be-visible.md
  - docs/adr/ADR-065-missing-path-must-fail.md
  - docs/adr/ADR.md
  - tests/test_phase2_5_integration.py
  - tests/test_phase_runner_missing_path.py
  - tools/scripts/hooks/phase_runner.py
  - tools/scripts/rules_engine/ast_fixer.py
  - uv.lock

## 更新记录: 2026-10-03 12:25:19

### 任务
Git 变更同步

### 变更摘要
- 变更文件 10 个 (+1518 / -209 行)
  - CHANGELOG.md
  - CONTEXT.md
  - ROADMAP.md
  - docs/adr/ADR-064-semantic-degradation-must-be-visible.md
  - docs/adr/ADR.md
  - tests/test_phase2_5_integration.py
  - tests/test_semantic_degraded_visibility.py
  - tools/scripts/hooks/phase_runner.py
  - tools/scripts/rules_engine/checker.py
  - uv.lock

## 更新记录: 2026-10-03 12:17:07

### 任务
Git 变更同步

### 变更摘要
- 变更文件 9 个 (+1494 / -192 行)
  - CHANGELOG.md
  - CONTEXT.md
  - ROADMAP.md
  - docs/adr/ADR-064-semantic-degradation-must-be-visible.md
  - docs/adr/ADR.md
  - tests/test_semantic_degraded_visibility.py
  - tools/scripts/hooks/phase_runner.py
  - tools/scripts/rules_engine/checker.py
  - uv.lock

## 更新记录: 2026-10-03 12:07:13

### 任务
Git 变更同步

### 变更摘要
- 变更文件 9 个 (+1477 / -162 行)
  - CHANGELOG.md
  - CONTEXT.md
  - ROADMAP.md
  - docs/adr/ADR-064-semantic-degradation-must-be-visible.md
  - docs/adr/ADR.md
  - tests/test_semantic_degraded_visibility.py
  - tools/scripts/hooks/phase_runner.py
  - tools/scripts/rules_engine/checker.py
  - uv.lock

## 更新记录: 2026-10-03 11:50:35

### 任务
Git 变更同步

### 变更摘要
- 变更文件 6 个 (+1435 / -129 行)
  - CHANGELOG.md
  - ROADMAP.md
  - docs/adr/ADR-064-semantic-degradation-must-be-visible.md
  - tests/test_semantic_degraded_visibility.py
  - tools/scripts/rules_engine/checker.py
  - uv.lock

## 更新记录: 2026-10-03 11:33:36

### 任务
Git 变更同步

### 变更摘要
- 变更文件 9 个 (+2055 / -229 行)
  - CHANGELOG.md
  - CONTEXT.md
  - ROADMAP.md
  - docs/adr/ADR-064-semantic-degradation-must-be-visible.md
  - docs/adr/ADR.md
  - tests/test_semantic_degraded_visibility.py
  - tests/test_semantic_rules_integration.py
  - tools/scripts/rules_engine/checker.py
  - uv.lock

## 更新记录: 2026-10-03 11:29:55

### 任务
Git 变更同步

### 变更摘要
- 变更文件 9 个 (+2038 / -208 行)
  - CHANGELOG.md
  - CONTEXT.md
  - ROADMAP.md
  - docs/adr/ADR-064-semantic-degradation-must-be-visible.md
  - docs/adr/ADR.md
  - tests/test_semantic_degraded_visibility.py
  - tests/test_semantic_rules_integration.py
  - tools/scripts/rules_engine/checker.py
  - uv.lock

## 更新记录: 2026-10-03 11:17:12

### 任务
Git 变更同步

### 变更摘要
- 变更文件 7 个 (+1631 / -237 行)
  - CHANGELOG.md
  - CONTEXT.md
  - ROADMAP.md
  - docs/adr/ADR.md
  - tests/test_semantic_rules_integration.py
  - tools/scripts/rules_engine/checker.py
  - uv.lock

## 更新记录: 2026-10-03 11:12:55

### 任务
Git 变更同步

### 变更摘要
- 变更文件 7 个 (+1616 / -222 行)
  - CHANGELOG.md
  - CONTEXT.md
  - ROADMAP.md
  - docs/adr/ADR.md
  - tests/test_semantic_rules_integration.py
  - tools/scripts/rules_engine/checker.py
  - uv.lock

## 更新记录: 2026-10-03 11:03:44

### 任务
Git 变更同步

### 变更摘要
- 变更文件 7 个 (+1601 / -207 行)
  - CHANGELOG.md
  - CONTEXT.md
  - ROADMAP.md
  - docs/adr/ADR.md
  - tests/test_semantic_rules_integration.py
  - tools/scripts/rules_engine/checker.py
  - uv.lock

## 更新记录: 2026-10-03 10:55:02

### 任务
Git 变更同步

### 变更摘要
- 变更文件 6 个 (+1568 / -189 行)
  - CHANGELOG.md
  - CONTEXT.md
  - ROADMAP.md
  - docs/adr/ADR.md
  - tools/scripts/rules_engine/checker.py
  - uv.lock

## 更新记录: 2026-10-03 02:16:00

### 任务
Git 变更同步

### 变更摘要
- 变更文件 4 个 (+1413 / -160 行)
  - CHANGELOG.md
  - CONTEXT.md
  - ROADMAP.md
  - uv.lock

## 更新记录: 2026-10-03 02:06:26

### 任务
Git 变更同步

### 变更摘要
- 变更文件 4 个 (+1448 / -226 行)
  - CHANGELOG.md
  - CONTEXT.md
  - ROADMAP.md
  - uv.lock

## 更新记录: 2026-10-03 02:01:33

### 任务
Git 变更同步

### 变更摘要
- 变更文件 5 个 (+1413 / -205 行)
  - CHANGELOG.md
  - CONTEXT.md
  - ROADMAP.md
  - docs/adr/ADR.md
  - uv.lock

## 更新记录: 2026-10-03 01:49:27

### 任务
Git 变更同步

### 变更摘要
- 变更文件 5 个 (+1513 / -283 行)
  - CHANGELOG.md
  - CONTEXT.md
  - ROADMAP.md
  - pyproject.toml
  - uv.lock

## 更新记录: 2026-10-03 01:38:59

### 任务
Git 变更同步

### 变更摘要
- 变更文件 5 个 (+1495 / -264 行)
  - CHANGELOG.md
  - CONTEXT.md
  - ROADMAP.md
  - pyproject.toml
  - uv.lock

## 更新记录: 2026-10-03 01:25:30

### 任务
Git 变更同步

### 变更摘要
- 变更文件 3 个 (+1454 / -240 行)
  - CONTEXT.md
  - pyproject.toml
  - uv.lock

## 更新记录: 2026-10-03 01:14:16

### 任务
Git 变更同步

### 变更摘要
- 变更文件 2 个 (+354 / -220 行)
  - CONTEXT.md
  - uv.lock

## 更新记录: 2026-10-03 01:07:27

### 任务
Git 变更同步

### 变更摘要
- 变更文件 11 个 (+727 / -370 行)
  - .jcode/hooks.json
  - CHANGELOG.md
  - CONTEXT.md
  - ROADMAP.md
  - docs/adr/ADR-062-fail-open-detector-validates-executability.md
  - docs/adr/ADR.md
  - pyproject.toml
  - tests/test_check_hooks_json_integrity.py
  - tools/scripts/check_hooks_json_integrity.sh
  - tools/scripts/rules_engine/ast_parser.py
  - uv.lock

## 更新记录: 2026-10-03 00:59:29

### 任务
Git 变更同步

### 变更摘要
- 变更文件 11 个 (+707 / -347 行)
  - .jcode/hooks.json
  - CHANGELOG.md
  - CONTEXT.md
  - ROADMAP.md
  - docs/adr/ADR-062-fail-open-detector-validates-executability.md
  - docs/adr/ADR.md
  - pyproject.toml
  - tests/test_check_hooks_json_integrity.py
  - tools/scripts/check_hooks_json_integrity.sh
  - tools/scripts/rules_engine/ast_parser.py
  - uv.lock

## 更新记录: 2026-10-03 00:44:43

### 任务
Git 变更同步

### 变更摘要
- 变更文件 9 个 (+367 / -285 行)
  - .jcode/hooks.json
  - CHANGELOG.md
  - CONTEXT.md
  - ROADMAP.md
  - docs/adr/ADR-062-fail-open-detector-validates-executability.md
  - docs/adr/ADR.md
  - tests/test_check_hooks_json_integrity.py
  - tools/scripts/check_hooks_json_integrity.sh
  - uv.lock

## 更新记录: 2026-10-03 00:27:01

### 任务
Git 变更同步

### 变更摘要
- 变更文件 7 个 (+299 / -261 行)
  - .jcode/hooks.json
  - CONTEXT.md
  - docs/adr/ADR-062-fail-open-detector-validates-executability.md
  - docs/adr/ADR.md
  - tests/test_check_hooks_json_integrity.py
  - tools/scripts/check_hooks_json_integrity.sh
  - uv.lock

## 更新记录: 2026-10-03 00:26:42

### 任务
Git 变更同步

### 变更摘要
- 变更文件 7 个 (+285 / -240 行)
  - .jcode/hooks.json
  - CONTEXT.md
  - docs/adr/ADR-062-fail-open-detector-validates-executability.md
  - docs/adr/ADR.md
  - tests/test_check_hooks_json_integrity.py
  - tools/scripts/check_hooks_json_integrity.sh
  - uv.lock

## 更新记录: 2026-10-03 00:18:46

### 任务
Git 变更同步

### 变更摘要
- 变更文件 6 个 (+207 / -190 行)
  - CONTEXT.md
  - docs/adr/ADR-062-fail-open-detector-validates-executability.md
  - docs/adr/ADR.md
  - tests/test_check_hooks_json_integrity.py
  - tools/scripts/check_hooks_json_integrity.sh
  - uv.lock

<!-- 滚动窗口: 已自动裁剪 1 条旧更新记录 -->
