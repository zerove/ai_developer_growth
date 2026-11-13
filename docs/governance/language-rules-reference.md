---
title: "Language Rules Reference"
description: "Complete reference for all code quality rule..."
category: 治理层
tags: ['AI', '开发者成长']
difficulty: 基础
---

# Language Rules Reference

Complete reference for all code quality rules across 26 languages and 5 frameworks.

## Overview

| Language | Rules | Error | Warning | Info |
|----------|-------|-------|---------|------|
| Python | 41 | 16 | 19 | 6 |
| TypeScript | 29 | 11 | 13 | 5 |
| Java | 37 | 15 | 18 | 4 |
| Go | 36 | 13 | 20 | 3 |
| Rust | 34 | 13 | 17 | 4 |
| C++ | 33 | 13 | 16 | 4 |
| C# | 33 | 14 | 15 | 4 |
| JavaScript | 41 | 18 | 19 | 4 |
| Kotlin | 33 | 13 | 18 | 2 |
| Swift | 17 | 7 | 8 | 2 |
| Scala | 33 | 11 | 15 | 7 |
| Ruby | 32 | 15 | 14 | 3 |
| PHP | 34 | 14 | 18 | 2 |
| Dart | 25 | 8 | 12 | 5 |
| Elixir | 25 | 7 | 11 | 7 |
| Lua | 28 | 9 | 14 | 5 |
| Haskell | 20 | 8 | 8 | 4 |
| Clojure | 20 | 5 | 8 | 7 |
| R | 27 | 9 | 11 | 7 |
| Perl | 28 | 13 | 13 | 2 |
| PowerShell | 28 | 10 | 13 | 5 |
| Zig | 28 | 9 | 13 | 6 |
| Assembly | 28 | 12 | 14 | 2 |
| Fortran | 19 | 8 | 7 | 4 |
| MATLAB | 27 | 10 | 14 | 3 |
| GraphQL | 19 | 6 | 10 | 3 |

**Total: 755 language rules + 18 common rules = 773 rules**

> 规则数量由 YAML 规则文件生成；完整规则以 `ai-dev-framework/languages/*/rules.d/anti_patterns.yml`
> 和 `ai-dev-framework/common/security.yml` 为准。其他语言表保留常用规则摘要。

## Rule ID Prefixes and Supersedes

规则 ID 全局唯一，语言前缀必须无歧义。26/26 个语言已严格标准化，前缀统一由
`rule_id_prefix()` 生成：Java/JavaScript/Ruby/Rust/TypeScript 使用
`java-`/`js-`/`rb-`/`rs-`/`ts-`，Clojure/C++/Dart/Elixir/Haskell/Kotlin/Lua/
PHP/PowerShell/Zig/Assembly/Fortran/GraphQL/MATLAB/Perl 使用
`clj-`/`cpp-`/`dt-`/`ex-`/`hs-`/`kt-`/`lua-`/`php-`/`ps-`/`zig-`/`asm-`/
`for-`/`gql-`/`mcl-`/`pl-`，C#/Go/Python/R/Scala/Swift 使用
`cs-`/`go-`/`py-`/`r-`/`sc-`/`sw-`。旧的 `ja-*` / `ru-*` / `ruby-*` /
`ty-*` / `cl-*` / `da-*` / `el-*` / `ha-*` / `cp-*` / `ko-*` / `lu-*` /
`ph-*` / `po-*` / `zi-*` / `as-*` / `fo-*` / `gr-*` / `ma-*` / `pe-*`
前缀已退役（2026-10-29），项目级 `.adg/rules.yml` 覆盖请改用新 ID。决策与影响
范围见 [ADR-080](../adr/ADR-080-canonical-rule-id-prefix.md)。

语言规则可用 `supersedes` 声明替代 `common/security.yml` 中的规则：

```yaml
- id: py-eval-exec
  supersedes:
  - common-eval-exec
```

加载器会丢弃被替代的 common 规则，但**不会**丢弃用户自定义规则。语言规则的
pattern 必须是 common 规则的超集，否则会丢失覆盖。当前 Python 侧使用该机制的规则包括
`py-eval-exec`、`py-hardcoded-secret`、`py-any-type`、`py-bare-except-pass` 和
`py-sql-string-format`。

校验命令：

```bash
python -m tools.scripts.check_rule_collisions
pytest tests/test_rule_supersedes_validation.py
```

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
| common-hardcoded-secret | error | `(?:password\|secret\|api_key\|token\|api_secret\|access_key\|private_key)\s*[=:]\s*["'][^"']{4,}["']` | Hardcoded secrets are a critical security vulnerability |
| common-eval-exec | error | `\beval\s*\(\|\bexec\s*\(\|\bFunction\s*\(` | Dynamic code execution is a security risk (code injection) |
| common-sql-injection | error | `f["'].*\b(SELECT\|INSERT\|UPDATE\|DELETE)\b.*\{` | SQL injection via f-string concatenation |
| common-unsafe-yaml-load | warning | `yaml\.load\((?!.*Loader)` | yaml.load() is unsafe - use yaml.safe_load() |
| common-pickle-load | error | `pickle\.loads?\(` | pickle deserialization is a security risk |
| common-ssl-verify-false | error | `verify\s*=\s*False` | SSL verification disabled - security risk |
| common-weak-hash | warning | `\bmd5\s*\(\|\bsha1\s*\(\|MD5\.\|SHA1\.\|hashlib\.md5\|hashlib\.sha1` | MD5 and SHA1 are cryptographically weak |
| common-http-url | warning | `http://[\w.-]+(?:/\|\s)` | Use HTTPS instead of HTTP for security |
| common-debugger | warning | `\bdebugger\b\|\bbreakpoint\s*\(\|\bpdb\.set_trace\s*\(\|\bimport\s+pdb\b` | Debugger statements should not be in production code |
| common-console-log | info | `console\.log\s*\(\|print\s*\(.*debug\|System\.out\.print\|puts\s+debug` | Debug output should be removed before production |
| common-todo | info | `#.*(?:TODO\|FIXME\|HACK\|XXX\|TEMP)` | Unresolved TODO/FIXME comment found |
| common-type-ignore | warning | `#\s*type:\s*ignore(?!\s*\[)` | Bare type ignore comment suppresses type checking; use specific error codes like |
| common-type-any | warning | `:\s*Any\b` | Use of Any type bypasses type checking |
| common-type-ignore-decorator | warning | `@\w+(?:\.\w+)*\.ignore` | Ignore decorator suppresses type checking |
| common-bare-except-pass | warning | `except\s*:\s*pass` | Bare except with pass swallows all exceptions |
| common-except-exception-pass | warning | `except\s+(?:Exception\|BaseException)\s*:\s*pass` | Catching broad exception and passing swallows errors |
| common-empty-except-block | warning | `except\s+(?:\w+(?:\s*,\s*\w+)*)?\s*:\s*\n\s*(?:pass\|#.*)?(?=\n\|$)` | Empty except block swallows errors silently |
| common-empty-catch | warning | `(?:catch\|except\|rescue)\s*(?:\([^)]+\))?\s*[:{]\s*(?:end\|[}\)])\s*$` | Empty catch block silently swallows errors |

## Python Rules (41 rules)

### Anti-patterns

| ID | Severity | Pattern | Message |
|----|----------|---------|---------|
| py-bare-except | error | `except\s*:` | Avoid bare except: use specific exception types |
| py-bare-except-pass | error | `except.*:\s*pass\b` | Never silently swallow exceptions |
| py-bare-except-string | error | `except\s+["']` | Do not use string exceptions - use exception classes |
| py-any-type | warning | `:\s*Any\b\|->\s*Any\b` | Avoid Any type - use specific types |
| py-union-none | info | `Optional\[` | In Python 3.10+, prefer X \| None over Optional[X] |
| py-mutable-default | error | `def\s+\w+\s*\(.*=\s*(\[\]\|\{\|set\()` | Mutable default arguments are shared across calls |
| py-eval-exec | error | `\beval\s*\(\|\bexec\s*\(` | eval/exec are security risks |
| py-hardcoded-secret | error | `(?:password\|secret\|api_key\|token\|api_secret\|access_key\|private_key)\s*[=:]\s*["'][^"']{4,}["']` | Hardcoded secrets are a security vulnerability |
| py-shell-true | warning | `subprocess\.\w+\(.*shell\s*=\s*True` | shell=True enables shell injection attacks |
| py-sql-string-format | error | `f["'][^"']*\b(?:SELECT\|INSERT\|UPDATE\|DELETE)\b.*\{\|(?:execute\|cursor\.execute)\s*\(.*(?:f["']\|\.format\(\|%\s)` | String formatting in SQL enables SQL injection |
| py-star-import | warning | `from\s+\S+\s+import\s+\*` | Wildcard imports pollute the namespace |
| py-global-statement | warning | `^\s*global\s+` | Global statements make code hard to test |
| py-print-statement | info | `^\s*print\s*\(` | Use logging module instead of print() |
| py-test-sleep | warning | `time\.sleep\(` | Sleep in tests makes them slow and flaky |
| py-missing-type-hints | warning | `def\s+[a-z]\w+\s*\([^)]*\)\s*:` | Public functions should have type annotations for parameters and return value |
| py-bare-raise | error | `^\s*raise\s*$` | Bare raise without arguments only works inside an except handler' |
| py-mutable-class-attr | warning | `class\s+\w+.*:\s*\n\s+\w+\s*=\s*(\[\]\|\{\|set\()` | Mutable class attributes are shared across all instances' |
| py-nested-import | info | `^\s+(?:from\s+\S+\s+)?import\s+\S+` | Import statements should be at the top of the file' |
| py-star-unpacking | info | `^\s*\w+,\s*\*\w+\s*=\s*\w+` | Star unpacking can obscure the structure of data' |
| py-complex-comprehension | warning | `\[.*for\s+.*in\s+.*\s+if\s+.*\s+if\s+.*\s+if\s+.*\]` | Comprehensions with >3 conditions are hard to read' |
| py-missing-all | info | `^(?!.*__all__)\s*(?:class\|def\|from)\s+\w+` | Public modules should define __all__ to control the public API' |
| py-log-sensitive | error | `log(?:ger)?\.(?:info\|debug\|warn\|error)\s*\(.*(?:password\|secret\|token\|credential\|api_key)` | Never log sensitive data (passwords, tokens, secrets) |
| py-log-print | warning | `^\s*print\s*\(` | Use structured logging instead of print statements in production |
| py-file-leak | info | `(?<!\bwith\s)(?:open\|fopen)\s*\([^)]*\)\s*(?!.*\b(with\|using\|close\|finally\|defer)\b)` | File handles must be closed properly to avoid resource leaks |
| py-connection-leak | error | `\b(?:connect\|new connection\|getConnection)\s*\([^)]*\)\s*(?!.*\b(with\|using\|close\|finally\|defer)\b)` | Database/network connections must be released after use |
| py-missing-await | error | `(?:async\s+def\|async\s+fn)\s+\w+\s*\([^)]*\)\s*\{?\s*$` | Async function called without await may cause race conditions |
| py-shared-mutable | warning | `(?:global\|static\|thread_local)\s+\w+(?:\s*=\s*[^;]*)?\s*[;]?$` | Shared mutable state without synchronization can cause race conditions |
| py-large-alloc-loop | warning | `(?:for\|while\|loop)\s*\([^)]*\)\s*\{?\s*[^}]*\b(?:append\|push\|concat\|new\s+(?:Array\|List\|StringBuilder))\b` | Repeated allocations inside loops impact performance |
| py-n-plus-one | warning | `(?:for\|while\|loop\|each\|map)\s*[^)]*\)?\s*\{?[^}]*\b(?:query\|find\|get\|fetch\|load)\b[^}]*\}` | Query inside a loop may cause N+1 performance problem |
| py-cors-allow-all | error | `(?:Access-Control-Allow-Origin\|origins?)\s*[=:]\s*["\']?\*["\']?` | Wildcard CORS exposes API to any origin |
| py-no-input-validation | warning | `(?:@\w+Mapping\|def\s+\w+\([^)]*request\|route\|endpoint\|api_view)` | API endpoints should validate all input parameters |
| py-hardcoded-origin | warning | `(?:allowed_origins\|trusted_origins\|ALLOWED_HOSTS)\s*[=:]\s*\["\'\]https?://` | Hardcoded origins in config should be environment variables |
| py-exception-leak | warning | `(?:print\|log\|logger)\s*\(.*e(?:rror)?\.(?:message\|to_String\|getMessage)\s*\)` | Exception messages may leak internal implementation details |
| py-hardcoded-secret-in-ci | error | `(?:GITHUB_TOKEN\|API_KEY\|SECRET\|PASSWORD)\s*[=:]\s*[\"'][^\"']+[\"']` | CI/CD secrets should use GitHub Secrets or vault, not hardcoded strings |
| py-ci-disabled-check | warning | `continue-on-error:\s*true` | CI checks with continue-on-error silently ignore failures |
| py-docker-image-latest | warning | `FROM\s+\S+:\s*latest\b` | Using :latest tag makes builds non-reproducible |
| py-docker-exposed-port | warning | `EXPOSE\s+\d+` | Exposed ports should have corresponding healthcheck |
| py-iac-hardcoded-secret | error | `(?:password\|secret_key\|access_key)\s*[=:]\s*[\"'][^\"']+[\"']` | Infrastructure secrets should use vault or secret store |
| py-iac-admin-exposed | error | `(?:adminer\|phpmyadmin\|pgadmin\|kibana)\s*:` | Admin tools should not be publicly accessible |
| py-docker-root-user | error | `FROM\s+\S+\s*(?:AS\s+\w+)?\s*\n(?!.*USER\s)` | Running containers as root is a security risk |
| py-pip-audit-missing | warning | `pip install\b(?!.*pip-audit\|.*safety)` | Package installation without vulnerability scanning |

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
python -m tools.scripts.validate_language_rules --all

# Validate specific language
python -m tools.scripts.validate_language_rules --lang python

# Auto-fix mode
python -m tools.scripts.validate_language_rules --all --fix

# Dry-run auto-fix
python -m tools.scripts.validate_language_rules --all --fix --dry-run

# Custom rules
python -m tools.scripts.validate_language_rules --all --custom-rules .ai-rules/

# HTML report
python -m tools.scripts.validate_language_rules --all --format html -o report.html

# SARIF output for GitHub Code Scanning
python -m tools.scripts.validate_language_rules --all --format sarif -o results.sarif

# JUnit XML for CI
python -m tools.scripts.validate_language_rules --all --format junit -o results.xml

# Threshold enforcement
python -m tools.scripts.validate_language_rules --all --max-errors 0 --max-warnings 10

# Incremental validation (cached)
python -m tools.scripts.validate_language_rules --all --incremental

# Specific files only
python -m tools.scripts.validate_language_rules --lang python --changed-files main.py,utils.py

# Health score
python -m tools.scripts.validate_language_rules --all --format json  # includes health_score
```

## Rule Test Framework

Validate rule regex patterns against test cases:

```bash
# Test specific language
python -m tools.scripts.validate_rule_tests --lang python

# Test all languages
python -m tools.scripts.validate_rule_tests --all
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
python -m tools.scripts.generate_fixes --all --dry-run

# Generate for specific language
python -m tools.scripts.generate_fixes --lang python -o fixes.json

# Apply fixes to YAML files
python -m tools.scripts.generate_fixes --lang python --apply
```

## Rule Marketplace

Discover, install, and manage rule packs:

```bash
# List available packs
python -m tools.scripts.rule_marketplace list

# Search rules
python -m tools.scripts.rule_marketplace search sql

# Install a pack
python -m tools.scripts.rule_marketplace install security --project-dir /path/to/project

# Validate installed rules
python -m tools.scripts.rule_marketplace validate --project-dir /path/to/project

# Export rules as shareable pack
python -m tools.scripts.rule_marketplace export --output my-pack.yml
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
python -m tools.scripts.validate_language_rules --all --format sarif -o results.sarif
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
