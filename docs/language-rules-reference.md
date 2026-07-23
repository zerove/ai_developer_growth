# Language Rules Reference

Complete reference for all code quality rules across 26 languages and 5 frameworks.

## Overview

| Language | Rules | Error | Warning | Info |
|----------|-------|-------|---------|------|
| Python | 21 | 12 | 6 | 3 |
| TypeScript | 17 | 9 | 5 | 3 |
| Java | 17 | 10 | 5 | 2 |
| Go | 16 | 8 | 6 | 2 |
| Rust | 15 | 7 | 5 | 3 |
| C++ | 8 | 4 | 3 | 1 |
| C# | 8 | 4 | 3 | 1 |
| JavaScript | 8 | 4 | 3 | 1 |
| Kotlin | 8 | 4 | 3 | 1 |
| Swift | 8 | 4 | 3 | 1 |
| Scala | 8 | 4 | 3 | 1 |
| Ruby | 8 | 4 | 3 | 1 |
| PHP | 8 | 4 | 3 | 1 |
| Dart | 8 | 4 | 3 | 1 |
| Elixir | 8 | 4 | 3 | 1 |
| Lua | 8 | 4 | 3 | 1 |
| Haskell | 8 | 4 | 3 | 1 |
| Clojure | 8 | 4 | 3 | 1 |
| R | 8 | 4 | 3 | 1 |
| Perl | 8 | 4 | 3 | 1 |
| PowerShell | 8 | 4 | 3 | 1 |
| Zig | 8 | 4 | 3 | 1 |
| Assembly | 8 | 4 | 3 | 1 |
| Fortran | 8 | 4 | 3 | 1 |
| MATLAB | 8 | 4 | 3 | 1 |
| GraphQL | 8 | 4 | 3 | 1 |

**Total: 262 rules across 26 languages**

## Frameworks

| Framework | Rules | Focus |
|-----------|-------|-------|
| React | 8 | Hooks, JSX, state management |
| Vue | 8 | Reactivity, composition, lifecycle |
| Django | 22 | Security, ORM, views, templates |
| FastAPI | 18 | Endpoints, dependency injection, async |
| Spring | 16 | DI, transactions, REST |

## Common Security Rules (All Languages)

| ID | Severity | Pattern | Message |
|----|----------|---------|---------|
| common-hardcoded-secret | error | `(?:password\|secret\|api_key\|token)\s*=\s*["'][^"']+["']` | Hardcoded secrets are a security risk |
| common-eval | error | `\beval\s*\(` | eval() allows arbitrary code execution |
| common-exec | error | `\bexec\s*\(` | exec() allows arbitrary code execution |
| common-sql-injection | error | String concat in SQL queries | Use parameterized queries |
| common-shell-injection | error | `os\.system\s*\(` | Use subprocess with shell=False |
| common-crypto-md5 | warning | `md5\s*\(` | MD5 is cryptographically weak |
| common-crypto-sha1 | warning | `sha1\s*\(` | SHA-1 is cryptographically weak |
| common-todo | info | `TODO\|FIXME` | Address before merging |

## Python Rules (21 rules)

### Anti-patterns

| ID | Severity | Pattern | Message |
|----|----------|---------|---------|
| py-bare-except | error | `except\s*:` | Avoid bare except |
| py-bare-except-pass | error | `except.*:\s*pass\s*$` | Never silently swallow exceptions |
| py-bare-except-string | error | `except\s+["']` | Use exception classes |
| py-any-type | warning | `:\s*Any\b` | Avoid Any type |
| py-union-none | info | `Optional\[X\]` | Use X \| None |
| py-mutable-default | error | `def.*=\s*(\[\]\|\{)` | Mutable default args shared |
| py-eval-exec | error | `\beval\s*\(\|exec\s*\(` | Security risk |
| py-hardcoded-secret | error | Password/secret patterns | Hardcoded secrets |
| py-shell-true | warning | `shell=True` | Shell injection risk |
| py-sql-string-format | error | SQL + f-string/format | SQL injection risk |
| py-pickle-untrusted | warning | `pickle\.loads` | Unsafe deserialization |
| py-assert-production | warning | `assert\s+` | Assert removed with -O |
| py-print-statement | info | `print\(` | Use logging module |
| py-global-import | warning | `from.*import \*` | Wildcard imports |
| py-mutable-attribute | warning | `self\.\w+\s*=\s*\[\]` | Shared mutable state |
| py-lambda-assignment | info | `lambda\s*=\|=\s*lambda` | Use def |
| py-complex-comprehension | info | Nested comprehensions | Simplify |
| py-redefined-unused | warning | Variable redefinition | Unused variable |
| py-shadowing-builtin | warning | Shadowing builtins | Use different name |
| py-todo | info | `TODO\|FIXME` | Address before merge |
| py-fixme | info | `FIXME` | Fix before merge |

## TypeScript Rules (17 rules)

### Anti-patterns

| ID | Severity | Pattern | Message |
|----|----------|---------|---------|
| ts-any-type | error | `:\s*any\b\|as\s+any` | Disables type checking |
| ts-unsafe-non-null | warning | `\w+!` | Bypasses null checks |
| ts-empty-catch | error | `catch.*\{\s*\}` | Silently swallows errors |
| ts-var-declaration | warning | `^\s*var\s+` | Use const/let |
| ts-require-import | warning | `require\(` | Use ES imports |
| ts-eqeq | warning | `==\|!=` | Use strict equality |
| ts-console-log | warning | `console\.log` | Remove from production |
| ts-any-assignment | error | `as any` | Disables type checking |
| ts-magic-number | info | Numeric literals | Use named constants |
| ts-nested-ternary | info | Ternary in ternary | Simplify |
| ts-long-function | info | Long functions | Break into smaller |
| ts-deep-nesting | info | Deep if/for nesting | Reduce complexity |
| ts-duplicate-code | info | Similar code blocks | Extract shared logic |
| ts-todo | info | `TODO\|FIXME` | Address before merge |
| ts-fixme | info | `FIXME` | Fix before merge |
| ts-hack | info | `HACK` | Refactor |
| ts-xxx | info | `XXX` | Marked for review |

## CLI Reference

```bash
# Validate all files in current directory
python tools/scripts/validate_language_rules.py --all

# Validate specific language
python tools/scripts/validate_language_rules.py --lang python

# Auto-fix mode
python tools/scripts/validate_language_rules.py --all --fix

# Dry-run auto-fix
python tools/scripts/validate_language_rules.py --all --fix --dry-run

# Custom rules
python tools/scripts/validate_language_rules.py --all --custom-rules .ai-rules/

# HTML report
python tools/scripts/validate_language_rules.py --all --format html -o report.html

# SARIF output for GitHub Code Scanning
python tools/scripts/validate_language_rules.py --all --format sarif -o results.sarif

# JUnit XML for CI
python tools/scripts/validate_language_rules.py --all --format junit -o results.xml

# Threshold enforcement
python tools/scripts/validate_language_rules.py --all --max-errors 0 --max-warnings 10

# Incremental validation (cached)
python tools/scripts/validate_language_rules.py --all --incremental

# Specific files only
python tools/scripts/validate_language_rules.py --lang python --changed-files main.py,utils.py

# Health score
python tools/scripts/validate_language_rules.py --all --format json  # includes health_score
```

## Rule Test Framework

Validate rule regex patterns against test cases:

```bash
# Test specific language
python tools/scripts/validate_rule_tests.py --lang python

# Test all languages
python tools/scripts/validate_rule_tests.py --all
```

Add `test_cases` to any rule in YAML:

```yaml
anti_patterns:
  - id: py-bare-except
    pattern: 'except\s*:'
    test_cases:
      - code: 'except:'
        should_match: true
      - code: 'except Exception:'
        should_match: false
```

## AI Fix Generator

Generate `fix_replacement` for rules that don't have one:

```bash
# Preview fixes
python tools/scripts/generate_fixes.py --all --dry-run

# Generate for specific language
python tools/scripts/generate_fixes.py --lang python -o fixes.json

# Apply fixes to YAML files
python tools/scripts/generate_fixes.py --lang python --apply
```

## Rule Marketplace

Discover, install, and manage rule packs:

```bash
# List available packs
python tools/scripts/rule_marketplace.py list

# Search rules
python tools/scripts/rule_marketplace.py search sql

# Install a pack
python tools/scripts/rule_marketplace.py install security --project-dir /path/to/project

# Validate installed rules
python tools/scripts/rule_marketplace.py validate --project-dir /path/to/project

# Export rules as shareable pack
python tools/scripts/rule_marketplace.py export --output my-pack.yml
```

### Available Packs

| Pack ID | Rules | Description |
|---------|-------|-------------|
| security | 8 | Cross-language security rules |
| python-pack | 21 | Python best practices |
| typescript-pack | 17 | TypeScript best practices |
| react-pack | 8 | React anti-patterns |
| vue-pack | 8 | Vue anti-patterns |
| django-pack | 22 | Django best practices |
| fastapi-pack | 18 | FastAPI best practices |
| spring-pack | 16 | Spring Boot best practices |
| full | 350 | All rules |

## Custom Rules

Create `.ai-rules/custom.yml` in your project root:

```yaml
anti_patterns:
  - id: custom-no-debug
    severity: error
    category: code_quality
    pattern: debugger
    message: Remove debugger statements
    fix_hint: Remove the debugger keyword

naming_conventions:
  - id: custom-prefix-req
    severity: warning
    category: naming
    pattern: "^class [^R]"
    message: All classes should start with 'R' prefix
```

Custom rules override base rules by matching `id`. Only the `severity` field can be overridden using `severity_override`:

```yaml
anti_patterns:
  - id: py-bare-except
    severity_override: warning  # Downgrade from error to warning
```

## Health Score

The health score (0-100) is calculated as:

- Start at 100
- Each error: -10 points
- Each warning: -3 points
- Each info: -1 point
- Minimum: 0

| Score | Grade | Meaning |
|-------|-------|---------|
| 90-100 | A | Excellent |
| 70-89 | B | Good |
| 50-69 | C | Fair |
| 30-49 | D | Poor |
| 0-29 | F | Critical |

## SARIF Output

SARIF (Static Analysis Results Interchange Format) output for GitHub Code Scanning:

```bash
python tools/scripts/validate_language_rules.py --all --format sarif -o results.sarif
```

The SARIF file can be uploaded to GitHub for inline PR annotations:

```yaml
# .github/workflows/code-quality.yml
- name: Upload SARIF
  uses: github/codeql-action/upload-sarif@v3
  with:
    sarif_file: results.sarif
```

## CI/CD Integration

See `.github/workflows/language-rules.yml` for a complete CI pipeline with:

- Matrix testing across 26 languages
- Custom rules support
- Threshold enforcement
- Linter aggregation (ruff, mypy, eslint, golangci-lint)
- SARIF upload for GitHub Code Scanning
- HTML/JSON/JUnit report artifacts
