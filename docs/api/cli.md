---
title: "CLI API"
description: "Unified CLI tools for AI Developer Growth project"
category: 工具层
tags: ['API', 'cli', 'tools']
difficulty: 基础
---

# CLI API

This document covers the unified CLI tools available in the project.

## hooks_runner.py - Unified Hook Runner

The primary CLI entry point for all quality checks, governance audits, and development workflows.

### Basic Checks

```bash
hooks_runner.py lint           # Run ruff lint check
hooks_runner.py format         # Run ruff format check
hooks_runner.py typecheck      # Run mypy type check (strict)
hooks_runner.py test           # Run pytest test suite
hooks_runner.py security       # Run security scan (bandit + pip-audit)
```

### Language Rules Validation

```bash
hooks_runner.py language-rules --path tools/scripts --lang python
hooks_runner.py language-rules --path . --fix
hooks_runner.py language-rules --jobs 4
```

Options:
- `--path PATH` - Path to validate (default: current directory)
- `--lang LANG` - Language (auto-detect if not specified)
- `--jobs, -j N` - Parallel workers (default: 1)
- `--fix` - Apply auto-fixes to fixable issues

### AI Quality Gate

```bash
hooks_runner.py quality-gate --path tools/scripts --full
hooks_runner.py quality-gate --check-security --check-type --format json
```

Options:
- `--path PATH` - Path to check (default: tools/scripts)
- `--full` - Run all checks
- `--check-annotation` - Check AI annotation
- `--check-security` - Check security patterns
- `--check-type` - Check type safety
- `--check-error` - Check error handling
- `--check-structure` - Check code structure
- `--check-patterns` - Check all anti-patterns
- `--format` - Output format: text, json (default: text)

### Governance Audit

```bash
hooks_runner.py governance-audit --full
hooks_runner.py governance-audit --validate-docs --check-ai-sdlc
```

Options:
- `--full` - Run all governance checks
- `--validate-docs` - Validate governance docs format
- `--check-ai-sdlc` - Check AI-SDLC compliance
- `--audit-hallucination` - Audit hallucination risks
- `--check-index` - Check index references

### Incremental Checks

```bash
hooks_runner.py diff --base HEAD      # Check only changed files vs base ref
hooks_runner.py pre-commit             # Pre-commit hook: check staged files only
```

Options:
- `--base REF` - Git ref to diff against (default: HEAD)

### Semantic Analysis (Tree-sitter AST)

```bash
hooks_runner.py semantic-check --path tools/scripts --lang python
hooks_runner.py semantic-check --jobs 4
```

Options:
- `--path PATH` - Path to check (default: current directory)
- `--lang LANG` - Language filter
- `--jobs, -j N` - Parallel workers (default: 1)

### AST-based Auto-fix

```bash
hooks_runner.py ast-fix --path tools/scripts --dry-run
hooks_runner.py ast-fix --path .
```

Options:
- `--path PATH` - Path to fix (default: current directory)
- `--dry-run` - Preview fixes without applying

Behavior notes:
- **Without `--dry-run`, files are actually rewritten** (ADR-066). Before
  that fix, `ASTFixer.fix_file` computed the fixed content but never wrote it
  back, so the command reported `✅ Fixes applied` while leaving every file
  untouched. Always pass `--dry-run` first if you want to inspect changes.
- The summary reports **three separate counts** (ADR-068), which are not
  always equal:
  - `Total fixes found: N (M auto-safe)` — how many issues were detected
  - `Fixes applied: K` — how many actually rewrote file content (`0` under
    `--dry-run`)
  - The conclusion line is chosen from `K`, not from `N`. When `N > 0` but
    `K == 0` the output says `review-only fix(es) reported, none applied
    automatically` rather than claiming success — rules marked
    `auto_safe=False` are reported for human review only (ADR-067).
- The exit code equals the number of **auto-safe** fixes on a single file, and
  `0` on a directory that had no file rejected. It is not a pass/fail signal,
  and it deliberately does *not* change under `--dry-run` (the dry-run count is
  "would-be-applied", not "applied"). On a directory, the exit code is `1` if
  **any** file was rejected by the syntax check (ADR-071) — the directory mode
  used to return `0` unconditionally, so a run that printed
  `❌ Syntax check failed` still exited `0` and CI judged it green.
- Before writing, every rewritten file is **syntax-checked** (ADR-070). If the
  fixed content does not parse, the write is refused entirely: the file keeps
  its original bytes, `Fixes applied` counts `0` for it, and the output names
  the specific error (`IndentationError: ...`). The summary line
  `❌ Syntax check failed` takes priority over `✅ Fixes applied`, so a run in
  which some files succeed and some are rejected still reports failure, and in
  directory mode that run also exits non-zero. Python is checked with
  `ast.parse`; other languages use tree-sitter, which is less sensitive to
  indentation-level problems — see ADR-070.
- If a file cannot be parsed, or writing it back fails, that file is skipped
  with a warning. Check the output rather than assuming coverage.

### AI Hallucination Pattern Scan

```bash
hooks_runner.py hallucination-scan --path tools/scripts
hooks_runner.py hallucination-scan --lang python
```

Options:
- `--path PATH` - Path to scan (default: current directory)
- `--lang LANG` - Language filter

### Git Hooks Installation

```bash
hooks_runner.py install-hooks --pre-push
hooks_runner.py install-hooks --pre-commit
```

### AI-driven Rule Generation

```bash
hooks_runner.py learn --project-path . --output custom_rules.yaml
hooks_runner.py learn --format json
```

Options:
- `project_path` - Project root (default: current directory)
- `--output, -o PATH` - Output rules YAML file
- `--format` - Output format: text, json (default: text)

### Quality Dashboard

```bash
hooks_runner.py dashboard --port 8765 --db adg_quality.db
```

Options:
- `--port N` - Port (default: 8765)
- `--db PATH` - SQLite database path (default: adg_quality.db)

### Full Check Suite

```bash
hooks_runner.py full
```

Runs all checks in optimized order (parallel lint+format+typecheck, then sequential test+security+quality-gate+governance-audit).

## adg_cli.py - ADG Governance CLI

```bash
python -m tools.scripts.adg_cli detect .
python -m tools.scripts.adg_cli check tools/scripts/ --lang python --severity error
python -m tools.scripts.adg_cli check tools/scripts/ --lang python --severity error --json > report.json
```

Options:
- `detect PATH` - Detect project language
- `check PATH` - Run governance checks
- `--lang LANG` - Language to check
- `--severity LEVEL` - Minimum severity: error, warning, info
- `--json` - Output JSON report

## validate_case_study.py - Case Study Validator

```bash
python -m tools.scripts.validate_case_study --path case-studies/
python -m tools.scripts.validate_case_study --path case-studies/my-case.md
```

Options:
- `--path PATH` - Path to case study file or directory

## validate_agent_definition.py - Agent Definition Validator

```bash
python -m tools.scripts.validate_agent_definition --path agents/
python -m tools.scripts.validate_agent_definition --path agents/knowledge-curator.md
```

Options:
- `--path PATH` - Path to agent definition file or directory

## validate_example_projects.py - Example Project Validator

```bash
python -m tools.scripts.validate_example_projects
```

Validates all example projects under `examples/` have proper structure.

## update_ai_tool_matrix.py - AI Tool Matrix Updater

```bash
python -m tools.scripts.update_ai_tool_matrix
```

Updates `docs/tools/ai-tool-matrix.md` from case studies.

## link_auditor.py - Link Auditor

```bash
python -m tools.scripts.link_auditor --path docs/
python -m tools.scripts.link_auditor --path docs/ --fix
```

Options:
- `--path PATH` - Path to audit (default: docs/)
- `--fix` - Attempt to fix broken links

## adr_generator.py - ADR Generator

```bash
python -m tools.scripts.adr_generator
# Interactive mode (default)
# Or LLM mode with LLM_PROVIDER and LLM_MODEL env vars
```

Modes:
- Interactive: Manual field-by-field input
- LLM: Auto-generate from title + brief description

## local_ci_mirror.py - 本地等价 CI

```bash
python -m tools.scripts.local_ci_mirror                 # 跑全部本地等价门禁
python -m tools.scripts.local_ci_mirror --list          # 列出清单
python -m tools.scripts.local_ci_mirror --only lint test # 只跑指定门禁
make ci-local                                          # 同上（Makefile 入口）
```

私有仓库的 GitHub Actions 消耗账户分钟配额，配额耗尽时 run 被立即拒绝
（job 被创建但 `steps` 全空），远端门禁**一次都没真正执行**（见 ADR-057）。
本脚本把远端 job 映射到本地可执行命令，逐项给出 PASS / FAIL / SKIP + 耗时：

- FAIL → 退出码非 0（与 CI 一致，阻断）；
- SKIP → **显式报告**（缺工具等），不静默放过；`--strict-skips` 可视为失败。

> 远端门禁存活探测请用 `hooks_runner ci-heartbeat`（pre-push 已接入，仅告警）。

## mkdocs_incremental.py - 文档增量构建

```bash
python -m tools.scripts.mkdocs_incremental            # 构建（输入未变且 site/ 已存在则跳过）
python -m tools.scripts.mkdocs_incremental --force    # 强制重建
python -m tools.scripts.mkdocs_incremental --check    # 只判断是否需要重建
```

按**内容指纹**（`docs/**/*.md` + `mkdocs.yml` + `templates/` + mkdocstrings 指令引用的
源码模块）判断文档是否需要重建：未变且 `site/` 已存在则跳过整构建，否则调
`mkdocs build --strict` 全量重建（正确性优先）。

> MkDocs 无"跳过未变更页面"的官方钩子：页面级缓存会让 material search 索引到
> 空内容（站内搜索失效），mkdocstrings 也必须真实导入源码。故只做整构建级别的
> 增量。详见 `docs/analysis/四维度深度分析.md` 的 P-03 行。

## adg check --cache - 增量缓存

```bash
adg check . --cache --json
```

复用未改动文件的检查结果（缓存实现与 `rules_engine` 同一 `CheckStore`），
JSON `meta` 上报真实命中/缺失：`cache_hits` / `cache_misses` / `cache_hit_rate` /
`cache_degraded`，未启用时这些计数为 `null`（不臆造 0）。

- 默认**不启用**缓存（不产生磁盘产物）；显式 `--cache` 才开启。
- 缓存键含生效规则签名：规则内容或 `--severity` 档位变化即失效重查。
- 缓存库路径：`[tool.adg].cache_db` > `<项目目录>/.adg/adg_check_cache.db`。
- 详见 `docs/adr/ADR-082-adg-check-uses-checkstore-cache.md`。

## adg cicd - CI/CD 配置生成

```bash
adg cicd --output ./
```

生成 CI/CD 配置文件（GitHub Actions 等）。旧文档里的 `cicd_dashboard.py`
脚本并不存在（见 `docs/analysis/四维度深度分析.md` 的 D-02 治理记录）。

## Quick Reference Card

| Tool | Purpose | Key Commands |
|------|---------|--------------|
| `hooks_runner.py` | Unified quality checks | `lint`, `format`, `typecheck`, `test`, `security`, `quality-gate`, `governance-audit`, `full` |
| `adg_cli.py` | Governance checks | `detect`, `check` |
| `validate_case_study.py` | Case study format | `--path` |
| `validate_agent_definition.py` | Agent definition format | `--path` |
| `validate_example_projects.py` | Example project structure | (no args) |
| `update_ai_tool_matrix.py` | Sync tool matrix from cases | (no args) |
| `link_auditor.py` | Check/fix broken links | `--path`, `--fix` |
| `adr_generator.py` | Create ADR documents | Interactive/LLM |
| `adg cicd` | 生成 CI/CD 配置 | `--output` |
