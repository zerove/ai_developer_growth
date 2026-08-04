# Gate 3: 自动化审计

> 语言无关的自动化审计标准

---

## 概述

Gate 3 是完全自动化的审计阶段，由 CI/CD 系统或预提交钩子自动执行。

---

## 审计流程

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Linter 检查  │────▶│  测试执行    │────▶│  安全扫描    │────▶│  报告生成    │
│  Gate 3.1    │     │  Gate 3.2   │     │  Gate 3.3   │     │  Gate 3.4   │
└──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
```

---

## 执行脚本

### 快速检查 (开发时)

```bash
# 使用框架检查脚本
bash .ai-framework/quality-gates/scripts/check.sh

# 或指定语言
bash .ai-framework/quality-gates/scripts/check.sh python
```

### 完整检查 (CI/CD)

```bash
# Linter
bash .ai-framework/languages/{language}/check.sh lint

# 测试
bash .ai-framework/languages/{language}/check.sh test

# 安全
bash .ai-framework/languages/{language}/check.sh security
```

---

## 集成方式

### opencode

```json
{
  "pre_commit": [
    {
      "name": "gate3-audit",
      "command": "bash .ai-framework/quality-gates/scripts/check.sh",
      "description": "Gate 3: 自动化审计"
    }
  ]
}
```

### GitHub Actions

```yaml
name: Gate 3 Audit
on: [push, pull_request]
jobs:
  audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run Gate 3
        run: bash .ai-framework/quality-gates/scripts/check.sh
```

---

## 检查项

| # | 检查项 | 工具 | 通过标准 |
|---|--------|------|----------|
| 3.1 | Linter 检查 | 语言特定 linter | 0 errors |
| 3.2 | 测试执行 | 语言特定测试框架 | 100% passed |
| 3.3 | 安全扫描 | 语言特定安全工具 | 0 critical |
| 3.4 | 报告生成 | CI/CD 系统 | JSON/Markdown |

---

## 审计结果格式

```json
{
  "gate": "gate3",
  "status": "passed",
  "timestamp": "2026-07-20T12:00:00Z",
  "checks": [
    {
      "name": "linter",
      "status": "passed",
      "errors": 0,
      "warnings": 2
    },
    {
      "name": "tests",
      "status": "passed",
      "total": 42,
      "passed": 42,
      "failed": 0
    },
    {
      "name": "security",
      "status": "passed",
      "critical": 0,
      "high": 0
    }
  ]
}
```

---

*本检查项适用于任何语言的自动化审计。*
