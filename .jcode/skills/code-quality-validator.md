# code-quality-validator

Validate code output against language-specific best practices, anti-patterns, and quality thresholds.

## When to Use

- After generating or modifying code in any language
- Before committing code changes
- When reviewing AI-generated code
- When setting up quality gates for a new project

## What It Does

1. **Detects language** and framework from project files
2. **Loads language-specific rules** from `ai-dev-framework/languages/`
3. **Validates code** against:
   - Anti-pattern detection (error handling, security, type safety, code quality)
   - Naming convention checks
   - Quantitative thresholds (function length, nesting depth, line length)
   - AST-based analysis (Python: complexity, type annotations)
4. **Reports issues** with severity, fix hints, and location
5. **Suggests fixes** for each detected issue

## Usage

```
/validate-code
```

Or explicitly:
- Validate a specific file: `validate_language_rules.py <file> --lang python`
- Validate entire project: `validate_language_rules.py <dir> --auto-detect`
- JSON output: `validate_language_rules.py <path> --json`

## Supported Languages

| Language   | Anti-Patterns | AST Checks | Naming | Thresholds |
|------------|:---:|:---:|:---:|:---:|
| Python     | 20  | 6   | 4   | 7   |
| TypeScript | 16  | -   | 6   | 7   |
| Rust       | 11  | -   | 7   | 6   |
| Go         | 11  | -   | 6   | 6   |

## Rule Categories

### Error Handling
Detects bare except, silent exception swallowing, unwrap/expect misuse, ignored errors.

### Security
Detects eval/exec, hardcoded secrets, SQL injection, XSS vulnerabilities, TLS bypass.

### Type Safety
Detects `any` types, mutable defaults, missing annotations, unsafe casts.

### Code Quality
Detects wildcard imports, global statements, console.log in production, var declarations.

### Readability
Enforces function length limits, nesting depth, line length, cyclomatic complexity.

## Workflow Integration

```
User Request → Generate Code → validate_language_rules.py → Fix Issues → Output
```

This skill integrates with the governance quality gates:
- **Gate 2** (Implementation): Anti-pattern check must pass
- **Gate 3** (Audit): Full validation suite runs in CI
