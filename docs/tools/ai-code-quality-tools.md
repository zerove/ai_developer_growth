---
title: AI 代码质量工具
description: 代码质量检查和优化工具
category: 工具层
tags: [AI, 代码质量, Lint]
difficulty: 初级
reading_time: 8 分钟
updated: 2026-07-21
---

# AI 代码质量工具

## 核心原则

代码质量 = 自动检查 + 持续改进 + 团队规范

## 工具分类

### 1. 静态分析

**Python:**
```
Ruff: 快速 Linter
MyPy: 类型检查
Pylint: 综合分析
```

**JavaScript:**
```
ESLint: 代码检查
Prettier: 代码格式化
TypeScript: 类型检查
```

### 2. 安全扫描

```
Bandit: Python 安全
npm audit: JavaScript 依赖
Snyk: 多语言安全
```

### 3. 复杂度分析

```
Radon: Python 复杂度
plato: JavaScript 复杂度
```

## 配置示例

### 1. Ruff 配置

```toml
# pyproject.toml
[tool.ruff]
line-length = 88
select = ["E", "F", "W", "I", "N", "UP"]

[tool.ruff.per-file-ignores]
"__init__.py" = ["F401"]
```

### 2. ESLint 配置

```json
{
  "extends": ["eslint:recommended"],
  "rules": {
    "no-unused-vars": "error",
    "no-console": "warn"
  }
}
```

### 3. MyPy 配置

```toml
# pyproject.toml
[tool.mypy]
python_version = "3.11"
strict = true
warn_return_any = true
```

## 最佳实践

### 1. CI 集成

```yaml
# GitHub Actions
- name: Lint
  run: ruff check .

- name: Type check
  run: mypy .
```

### 2. Pre-commit

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    hooks:
      - id: ruff
      - id: ruff-format
```

### 3. IDE 集成

```
VS Code: 安装扩展
JetBrains: 内置支持
Vim: 插件支持
```

## 效率提升

### 1. 自动修复

```bash
ruff check --fix .
prettier --write .
```

### 2. 增量检查

只检查修改的文件。

### 3. 团队规范

建立统一的代码规范。

---

*最后更新: 2026-07-21*
