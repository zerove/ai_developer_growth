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
  `0` on a directory. It is not a pass/fail signal, and it deliberately does
  *not* change under `--dry-run` (the dry-run count is "would-be-applied",
  not "applied").
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
python tools/scripts/validate_case_study.py --path case-studies/
python tools/scripts/validate_case_study.py --path case-studies/my-case.md
```

Options:
- `--path PATH` - Path to case study file or directory

## validate_agent_definition.py - Agent Definition Validator

```bash
python tools/scripts/validate_agent_definition.py --path agents/
python tools/scripts/validate_agent_definition.py --path agents/knowledge-curator.md
```

Options:
- `--path PATH` - Path to agent definition file or directory

## validate_example_projects.py - Example Project Validator

```bash
python tools/scripts/validate_example_projects.py
```

Validates all example projects under `examples/` have proper structure.

## update_ai_tool_matrix.py - AI Tool Matrix Updater

```bash
python tools/scripts/update_ai_tool_matrix.py
```

Updates `docs/tools/ai-tool-matrix.md` from case studies.

## link_auditor.py - Link Auditor

```bash
python tools/scripts/link_auditor.py --path docs/
python tools/scripts/link_auditor.py --path docs/ --fix
```

Options:
- `--path PATH` - Path to audit (default: docs/)
- `--fix` - Attempt to fix broken links

## adr_generator.py - ADR Generator

```bash
python tools/scripts/adr_generator.py
# Interactive mode (default)
# Or LLM mode with LLM_PROVIDER and LLM_MODEL env vars
```

Modes:
- Interactive: Manual field-by-field input
- LLM: Auto-generate from title + brief description

## cicd_dashboard.py - CI/CD Dashboard

```bash
python tools/scripts/cicd_dashboard.py --db cicd_metrics.db
```

Starts a web dashboard for CI/CD metrics visualization.

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
| `cicd_dashboard.py` | CI/CD metrics dashboard | `--db` |
