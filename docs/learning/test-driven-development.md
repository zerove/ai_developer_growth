---
title: 测试驱动开发
description: TDD 的原理和实践方法
category: 学习层
tags: [TDD, 测试, 开发流程]
difficulty: 进阶
reading_time: 12 分钟
updated: 2026-07-21
---

# 测试驱动开发

## 核心原则

TDD = 红 → 绿 → 重构

```
写失败的测试 → 写通过的代码 → 重构优化
```

## TDD 流程

### 1. 红阶段 (Red)

**任务:** 写一个失败的测试

**原则:**
- 测试要小
- 测试要具体
- 测试要独立

**示例:**
```python
def test_add():
    assert add(1, 2) == 3  # 失败
```

### 2. 绿阶段 (Green)

**任务:** 写最少代码让测试通过

**原则:**
- 不要过度设计
- 优先让测试通过
- 可以写简单实现

**示例:**
```python
def add(a, b):
    return a + b  # 通过
```

### 3. 重构阶段 (Refactor)

**任务:** 优化代码结构

**原则:**
- 保持测试通过
- 消除重复
- 提升可读性

**示例:**
```python
def add(a: int, b: int) -> int:
    """两数相加"""
    return a + b
```

## TDD 实践

### 1. 测试先行

**步骤:**
1. 理解需求
2. 写测试
3. 实现功能
4. 重构代码

### 2. 小步前进

**原则:**
- 每次只改一点
- 每步都测试
- 频繁提交

### 3. 测试金字塔

```
        /  E2E  \
       / 集成测试 \
      /  单元测试  \
```

**比例:**
- 单元测试: 70%
- 集成测试: 20%
- E2E 测试: 10%

## 测试技巧

### 1. 测试命名

**格式:**
```python
def test_[功能]_[条件]_[结果]():
    ...
```

**示例:**
```python
def test_add_positive_numbers_returns_sum():
    assert add(1, 2) == 3

def test_add_negative_numbers_returns_sum():
    assert add(-1, -2) == -3
```

### 2. 测试结构

**AAA 模式:**
```python
def test_example():
    # Arrange
    input_data = [1, 2, 3]
    
    # Act
    result = process(input_data)
    
    # Assert
    assert result == [2, 3, 4]
```

### 3. Mock 和 Stub

**Mock 外部依赖:**
```python
from unittest.mock import Mock, patch

def test_with_mock():
    with patch('module.external_api') as mock_api:
        mock_api.return_value = {'status': 'ok'}
        result = call_external_api()
        assert result == {'status': 'ok'}
```

## TDD 好处

| 好处 | 说明 |
|------|------|
| **设计更好** | 测试驱动设计 |
| **缺陷更少** | 测试覆盖全面 |
| **重构安全** | 有测试保护 |
| **文档作用** | 测试即文档 |

## AI 辅助 TDD

```markdown
请帮我实现 TDD:

1. 根据需求写测试
2. 实现功能代码
3. 重构优化
4. 确保测试通过
```

## 案例: TDD 实践

### 需求
实现一个字符串计算器

### TDD 过程

**测试 1:**
```python
def test_empty_string_returns_zero():
    assert add("") == 0
```

**实现 1:**
```python
def add(numbers: str) -> int:
    return 0
```

**测试 2:**
```python
def test_single_number():
    assert add("1") == 1
```

**实现 2:**
```python
def add(numbers: str) -> int:
    if not numbers:
        return 0
    return int(numbers)
```

### 结果
- 测试覆盖率: 100%
- 代码质量: 高
- 可维护性: 好

---

*最后更新: 2026-07-21*
