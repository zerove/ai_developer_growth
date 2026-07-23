# ADR-002: Refactoring validate_language_rules.py into Modules

## Status

Proposed

## Date

2026-07-23

## Context

`validate_language_rules.py` has grown to 2160 lines with 40+ functions covering:
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

This makes it hard to navigate, test in isolation, and maintain.

## Decision

Refactor into a `rules/` package:

```
tools/scripts/rules/
  __init__.py         # Public API re-exports
  loader.py           # load_rules(), load_custom_rules(), _merge_rules()
  checker.py          # check_anti_patterns(), check_naming_conventions()
  complexity.py       # check_thresholds(), nesting analysis
  python_ast.py       # check_python_ast(), cyclomatic complexity
  fixer.py            # apply_fixes()
  reporters.py        # JUnit, HTML, SARIF generation
  health.py           # calculate_health_score()
  cache.py            # file_hash, load/save cache
  linters.py          # ruff, mypy, eslint, golangci-lint
  models.py           # Issue, ValidationResult, FixResult, HealthScore
```

### Migration Strategy

1. Create `rules/` package with thin wrappers
2. Move functions one module at a time
3. Keep backward-compatible imports in validate_language_rules.py
4. Update tests incrementally

## Consequences

### Positive
- Each module is independently testable
- Easier to find specific functionality
- Clearer dependency graph
- Enables lazy loading

### Negative
- Breaking change for direct imports (mitigated by re-exports)
- More files to navigate
- Import paths change

## Follow-up

- Implement in Phase 8
- Add module-level tests
