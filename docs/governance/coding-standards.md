---
title: 代码规范标准
description: 代码编写规范和最佳实践
category: 治理层
tags: [代码规范, 最佳实践, 团队]
difficulty: 基础
reading_time: 10 分钟
updated: 2026-07-21
---

# 代码规范标准

## 核心原则

代码规范 = 可读性 + 一致性 + 可维护性

## Python 规范

### 1. PEP 8

```
缩进: 4 空格
行宽: 79 字符
命名: snake_case
导入: 按类型分组
```

### 2. 类型注解

```python
def process_order(order_id: int, user_id: int) -> dict:
    """处理订单"""
    ...
```

### 3. 文档字符串

```python
def calculate_discount(price: float, discount: float) -> float:
    """
    计算折扣后的价格
    
    Args:
        price: 原价
        discount: 折扣率 (0-1)
    
    Returns:
        折扣后的价格
    
    Raises:
        ValueError: 当折扣率不在 0-1 范围内
    """
    ...
```

## JavaScript/TypeScript 规范

### 1. ESLint 配置

```json
{
  "extends": ["eslint:recommended"],
  "rules": {
    "no-unused-vars": "error",
    "no-console": "warn",
    "prefer-const": "error"
  }
}
```

### 2. TypeScript 严格模式

```json
{
  "compilerOptions": {
    "strict": true,
    "noImplicitAny": true,
    "strictNullChecks": true
  }
}
```

## 通用规范

### 1. 命名规范

```
变量: camelCase (JS) / snake_case (Python)
常量: UPPER_SNAKE_CASE
类: PascalCase
文件: kebab-case
```

### 2. 注释规范

```
解释为什么，而不是做什么
及时更新注释
避免无用注释
```

### 3. 错误处理

```python
try:
    result = process_data(data)
except ValueError as e:
    logger.error(f"处理数据失败: {e}")
    raise
except Exception as e:
    logger.exception("未知错误")
    raise
```

## 自动化检查

### 1. Linter

```bash
# Python
ruff check .
ruff format .

# JavaScript
eslint .
prettier --check .
```

### 2. Pre-commit

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    hooks:
      - id: ruff
      - id: ruff-format
```

### 3. CI 集成

```yaml
- name: Lint
  run: ruff check .
- name: Format check
  run: ruff format --check .
```

## 团队协作

### 1. 代码审查

```
检查代码规范
检查逻辑正确性
检查测试覆盖
```

### 2. 文档更新

```
README 更新
API 文档更新
变更日志更新
```

### 3. 知识共享

```
技术分享
最佳实践文档
新人培训
```

---

*最后更新: 2026-07-21*
