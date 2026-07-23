# ADR-002: Refactoring validate_language_rules.py into Modules

## Status

Accepted (Implemented 2026-07-23)

## Date

2026-07-23

## Context

`validate_language_rules.py` grew to 2166 lines with 50 functions covering:
- Rule loading and merging
- Anti-pattern detection
- Naming convention checking
- Complexity analysis
- Python AST analysis
- Auto-fix engine
- Report generation (JUnit/HTML/SARIF)
- Health scoring
- Linter aggregation
- File caching

This made it hard to navigate, test in isolation, and maintain.

## Decision

Refactor into a `rules_engine/` package with a unified `hooks_runner.py` entry point:

```
tools/scripts/rules_engine/
  __init__.py              # Public API + docstring examples
  models.py                # Issue, CheckResult, Severity, HealthScore
  rule_loader.py           # load_rules(), disk cache, YAML merging
  anti_pattern_checker.py  # Regex-based anti-pattern detection
  naming_checker.py        # Naming convention validation
  complexity_checker.py    # AST complexity (Python) + regex (JS/TS)
  security_patterns.py     # Cross-language security/type/error patterns
  checker.py               # Main orchestrator + external linter integration

tools/scripts/hooks_runner.py    # Unified CLI entry point
tools/scripts/report_generator.py # JUnit/HTML/SARIF report generation
tools/scripts/fix_applier.py      # Auto-fix engine
```

### Migration Strategy (Completed)

1. Created `rules_engine/` package with modular checkers
2. Created `hooks_runner.py` as unified entry point (lint, format, typecheck, test, security, quality-gate, governance-audit)
3. Extracted `report_generator.py` and `fix_applier.py` from validate_language_rules.py
4. Updated `validate_language_rules.py` to delegate to new modules (backward-compatible)
5. Updated CI/CD to use `hooks_runner.py`
6. Added 82 new unit tests (748 -> 830 total)

## Consequences

### Positive
- Each module is independently testable (55 new tests for rules_engine)
- hooks_runner.py reduced full check time via parallelization (lint+format+typecheck concurrent)
- Clearer dependency graph
- Disk cache for rule loading across CLI invocations
- Unified entry point for CI/CD and pre-commit hooks

### Negative
- More files to navigate (7 modules vs 1 monolith)
- Import paths changed (mitigated by re-exports in validate_language_rules.py)

## Metrics

| Metric | Before | After |
|--------|--------|-------|
| validate_language_rules.py | 2166 lines | 1930 lines (-11%) |
| rules_engine modules | 0 | 7 modules |
| Test count | 748 | 830 (+82) |
| hooks_runner.py | N/A | 560 lines |
| Report generators | inline | 232 lines (report_generator.py) |
| Fix applier | inline | 85 lines (fix_applier.py) |
