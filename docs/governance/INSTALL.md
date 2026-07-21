---
title: Governance Installation Guide
description: > How to add AI agent development governance to any project.
category: 治理层
tags: ['AI', 'Python', '测试', 'TypeScript', 'CI/CD']
difficulty: 初级
reading_time: 10 分钟
updated: 2026-07-21
---

# Governance Installation Guide

> How to add AI agent development governance to any project.

---

## Quick Start (30 seconds)

```bash
# Option 1: Copy governance files manually
cp GOVERNANCE.md /path/to/your/project/
mkdir -p /path/to/your/project/docs/governance/languages
cp docs/governance/languages/{python,rust,typescript,go}.md /path/to/your/project/docs/governance/languages/

# Option 2: Use the install script (if available)
curl -sSL https://raw.githubusercontent.com/your-repo/install-governance.sh | bash -s /path/to/your/project
```

---

## What You Get

| File | Purpose | Required? |
|------|---------|-----------|
| `GOVERNANCE.md` | Universal governance standard | Yes |
| `CLAUDE.md` | Agent system instructions | Recommended |
| `CONTEXT.md` | Project state snapshot | Yes |
| `ADR.md` | Architecture decisions | Recommended |
| `AGENTS.md` | Agent definitions | Optional |
| `docs/governance/languages/*.md` | Language-specific rules | Optional |

---

## Step-by-Step Installation

### Step 1: Copy Core Files

```bash
# Navigate to your project
cd /path/to/your/project

# Copy the universal governance standard
cp /path/to/ai_developer_growth/GOVERNANCE.md .

# Create context files
cat > CONTEXT.md << 'EOF'
# Project Context

## Overview
{One sentence description of your project}

## Current State
- Version: 0.1.0
- Progress: 0%
- Current iteration: Initial setup

## Completed Modules
- None yet

## In Progress
- Project setup

## Key Decisions
- None yet

## Known Issues
- None yet

## Next Steps
- Initial development
EOF

cat > ADR.md << 'EOF'
# Architecture Decision Records

> Record significant architectural decisions here.
EOF
```

### Step 2: Create Agent Instructions (CLAUDE.md)

```bash
cat > CLAUDE.md << 'EOF'
# {Project Name}: Agent Development Governance

> All AI agents working in this project must follow these standards.

---

## Project Context
{Paste CONTEXT.md content here}

## Governance Standard
Follow the rules in `GOVERNANCE.md`:

1. **Agent Definitions**: Use the template in GOVERNANCE.md Section 2
2. **Workflow**: Follow the 5-step lifecycle in Section 3
3. **Quality Gates**: Pass all 4 gates before merging (Section 4)
4. **Code Standards**: Follow language-specific rules in Section 5
5. **Context Management**: Update CONTEXT.md after major changes

## Language-Specific Rules
{Copy rules from docs/governance/languages/{your-language}.md here}

## Verification Commands
{Copy verification commands from GOVERNANCE.md Section 10 and adapt}

## Forbidden Actions
- Never use unwrap()/expect() in production code
- Never skip quality gates
- Never commit without running tests
- Never ignore type errors
EOF
```

### Step 3: Set Up CI/CD (Optional)

```yaml
# .github/workflows/governance.yml
name: Governance Quality Gates

on:
  pull_request:
    branches: [main]
  push:
    branches: [main]

jobs:
  gate2-code-quality:
    name: "Gate 2: Code Quality"
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Check code standards
        run: |
          # Adapt these commands to your language
          grep -rn "unwrap()\|expect()" src/ || true
          find src/ -type f -exec wc -l {} + | awk '$1 > 300 {print}'

  gate3-automated-audit:
    name: "Gate 3: Automated Audit"
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run linter
        run: {your_linter_command}
      - name: Run type checker
        run: {your_type_checker_command}
      - name: Run tests
        run: {your_test_command}
```

### Step 4: Configure Pre-commit Hooks (Optional)

```bash
# Install pre-commit
pip install pre-commit

# Create .pre-commit-config.yaml
cat > .pre-commit-config.yaml << 'EOF'
repos:
  - repo: local
    hooks:
      - id: governance-gate2
        name: Governance Gate 2
        entry: bash -c 'grep -rn "unwrap()\|expect()" src/ && exit 1 || true'
        language: system
        files: \.rs$
        pass_filenames: false
EOF

# Install hooks
pre-commit install
```

---

## Language-Specific Setup

### Python

```bash
# Copy Python governance rules
cp docs/governance/languages/python.md docs/governance/

# Add to your tooling
pip install ruff mypy pytest pytest-cov

# Add to pyproject.toml
cat >> pyproject.toml << 'EOF'
[tool.ruff]
line-length = 88
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP"]

[tool.mypy]
strict = true

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-v --cov=src --cov-report=term-missing"
EOF
```

### Rust

```bash
# Copy Rust governance rules
cp docs/governance/languages/rust.md docs/governance/

# Add to Cargo.toml
cat >> Cargo.toml << 'EOF'

[lints.clippy]
unwrap_used = "deny"
expect_used = "deny"
panic = "deny"
EOF

# Create rustfmt.toml
cat > rustfmt.toml << 'EOF'
max_width = 100
tab_spaces = 4
EOF

# Create clippy.toml
cat > clippy.toml << 'EOF'
unwrap-handling-allowed = false
EOF
```

### TypeScript

```bash
# Copy TypeScript governance rules
cp docs/governance/languages/typescript.md docs/governance/

# Add to tsconfig.json
cat > tsconfig.json << 'EOF'
{
  "compilerOptions": {
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "noImplicitReturns": true,
    "noFallthroughCasesInSwitch": true
  }
}
EOF

# Add to .eslintrc.js
cat > .eslintrc.js << 'EOF'
module.exports = {
  extends: [
    'eslint:recommended',
    'plugin:@typescript-eslint/recommended',
    'plugin:@typescript-eslint/recommended-requiring-type-checking'
  ],
  rules: {
    '@typescript-eslint/no-explicit-any': 'error',
    '@typescript-eslint/no-unused-vars': 'error'
  }
};
EOF
```

### Go

```bash
# Copy Go governance rules
cp docs/governance/languages/go.md docs/governance/

# Create .golangci.yml
cat > .golangci.yml << 'EOF'
linters:
  enable:
    - errcheck
    - gosimple
    - govet
    - ineffassign
    - staticcheck
    - unused
    - gocritic
    - gofmt
    - goimports

linters-settings:
  errcheck:
    check-blank: true
  gocritic:
    enabled-tags:
      - diagnostic
      - style
      - performance

issues:
  exclude-rules:
    - path: _test\.go
      linters:
        - errcheck
EOF
```

---

## Verification

After installation, verify everything works:

```bash
# Check governance files exist
ls -la GOVERNANCE.md CLAUDE.md CONTEXT.md ADR.md

# Check language-specific rules
ls -la docs/governance/languages/

# Run your first quality gate check
# (Adapt commands to your language)
grep -rn "unwrap()\|expect()" src/ || echo "Gate 2: PASS"
```

---

## Customization

### Adding Custom Rules

1. Edit `CLAUDE.md` to add project-specific instructions
2. Edit `CONTEXT.md` to reflect your project state
3. Add language-specific rules to `docs/governance/languages/`

### Removing Unused Sections

If you don't need certain sections (e.g., ADR.md), simply don't create those files. The governance system is modular - use what you need.

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "GOVERNANCE.md not found" | Ensure the file is in your project root |
| "CLAUDE.md not found" | Create it with the template above |
| "CONTEXT.md outdated" | Update it after major changes |
| "Gate 2 failing" | Fix code quality issues before committing |
| "Gate 3 failing" | Run linter/type checker/tests locally first |

---

## Next Steps

1. Read `GOVERNANCE.md` to understand the full standard
2. Adapt language-specific rules in Section 5
3. Set up CI/CD with the governance workflow
4. Train your team on the new standards
5. Monitor quality metrics over time

---

*Governance is a journey, not a destination. Start with the basics and evolve.*
