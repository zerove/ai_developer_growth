---
title: "Rules Engine API"
description: "Language-agnostic code quality rules engine with modular checkers"
category: 工具层
tags: ['API', 'rules-engine', 'code-quality']
difficulty: 基础
---

# Rules Engine API

The Rules Engine is a modular, language-agnostic code quality validation system supporting 26+ languages with YAML-defined rules.

## Core Modules

### Checker (Main Orchestrator)

::: tools.scripts.rules_engine.checker
    options:
      show_source: false
      members:
        - check_file
        - check_directory
        - CheckResult
        - CheckOptions

### Models

::: tools.scripts.rules_engine.models
    options:
      show_source: false
      members:
        - Issue
        - CheckResult
        - Severity
        - HealthScore
        - LanguageRules

### Rule Loader

::: tools.scripts.rules_engine.rule_loader
    options:
      show_source: false
      members:
        - load_rules
        - load_rules_for_language
        - merge_rules
        - get_rule_cache_path

### Anti-Pattern Checker

::: tools.scripts.rules_engine.anti_pattern_checker
    options:
      show_source: false
      members:
        - check_anti_patterns
        - AntiPatternChecker

### Naming Checker

::: tools.scripts.rules_engine.naming_checker
    options:
      show_source: false
      members:
        - check_naming_conventions
        - NamingChecker

### Complexity Checker

::: tools.scripts.rules_engine.complexity_checker
    options:
      show_source: false
      members:
        - check_complexity
        - ComplexityChecker
        - calculate_cyclomatic_complexity
        - calculate_cognitive_complexity

### Security Patterns

::: tools.scripts.rules_engine.security_patterns
    options:
      show_source: false
      members:
        - get_security_rules
        - SecurityPatternChecker
        - check_security_patterns

### Auto Fix

::: tools.scripts.rules_engine.auto_fix
    options:
      show_source: false
      members:
        - apply_fixes_to_directory
        - apply_fixes_to_file
        - format_fix_results
        - FixResult

### Report Generator

::: tools.scripts.report_generator
    options:
      show_source: false
      members:
        - generate_junit_report
        - generate_html_report
        - generate_sarif_report
        - ReportGenerator

### Fix Applier

::: tools.scripts.fix_applier
    options:
      show_source: false
      members:
        - FixApplier
        - apply_fix
        - preview_fix

### AST Fixer

::: tools.scripts.rules_engine.ast_fixer
    options:
      show_source: false
      members:
        - ASTFixer
        - FixReport
        - format_fix_report

### Hallucination Detector

::: tools.scripts.rules_engine.hallucination_detector
    options:
      show_source: false
      members:
        - detect_hallucinations
        - detect_hallucinations_in_file
        - format_hallucination_report
        - HallucinationReport
        - HallucinationFinding

### AI Rules Generator

::: tools.scripts.rules_engine.ai_rules_generator
    options:
      show_source: false
      members:
        - analyze_project
        - format_analysis
        - generate_rules_yaml

## CLI Entry Point

The unified CLI is provided by `hooks_runner.py`:

```bash
# Basic checks
hooks_runner.py lint
hooks_runner.py format
hooks_runner.py typecheck
hooks_runner.py test
hooks_runner.py security

# Language rules
hooks_runner.py language-rules --path tools/scripts --lang python
hooks_runner.py language-rules --path . --fix

# Quality gate
hooks_runner.py quality-gate --path tools/scripts --full
hooks_runner.py quality-gate --check-security --check-type --format json

# Governance audit
hooks_runner.py governance-audit --full
hooks_runner.py governance-audit --validate-docs --check-ai-sdlc

# Incremental checks
hooks_runner.py diff --base HEAD
hooks_runner.py pre-commit

# Semantic analysis
hooks_runner.py semantic-check --path tools/scripts --lang python
hooks_runner.py ast-fix --path tools/scripts --dry-run
hooks_runner.py hallucination-scan --path tools/scripts

# Full suite
hooks_runner.py full
```

## Configuration

Rules are defined in YAML files under `tools/scripts/rules/`:
- `python.yaml` - Python-specific rules
- `javascript.yaml` - JavaScript/TypeScript rules
- `go.yaml` - Go rules
- `rust.yaml` - Rust rules
- `common.yaml` - Cross-language rules
- `security.yaml` - Security patterns

## Example: Custom Rule

```yaml
# .adg/rules.yml
rules:
  - id: no-print-statements
    pattern: "print\\("
    message: "Avoid print() statements; use logging instead"
    severity: warning
    languages: ["python"]
    categories: ["style", "logging"]
```
