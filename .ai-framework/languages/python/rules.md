# Python 语言规则

> 适用于 Python 项目的 AI Agent 开发规则

---

## 代码风格

### 命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| 文件名 | snake_case | `my_module.py` |
| 函数名 | snake_case | `my_function()` |
| 变量名 | snake_case | `my_variable` |
| 类名 | PascalCase | `MyClass` |
| 常量 | UPPER_SNAKE_CASE | `MAX_SIZE` |
| 私有 | 单下划线前缀 | `_private_method()` |

### 导入顺序

```python
# 1. 标准库
import os
import sys
from pathlib import Path

# 2. 第三方库
import requests
from flask import Flask

# 3. 本地模块
from .my_module import my_function
```

---

## 错误处理

### 惯用模式

```python
# ✅ 正确
try:
    result = do_something()
except ValueError as e:
    logger.error(f"Invalid value: {e}")
    raise
except Exception as e:
    logger.error(f"Unexpected error: {e}")
    raise

# ❌ 错误
try:
    result = do_something()
except:
    pass
```

---

## 测试

### 框架选择

| 框架 | 适用场景 |
|------|----------|
| pytest | 通用测试 |
| unittest | 需要类测试 |
| hypothesis | 属性测试 |

### 测试结构

```python
# tests/test_my_module.py
import pytest
from my_module import my_function

def test_my_function_success():
    result = my_function(1, 2)
    assert result == 3

def test_my_function_error():
    with pytest.raises(ValueError):
        my_function(None, 2)
```

---

## 文档

### 文档字符串

```python
def my_function(param1: int, param2: str) -> bool:
    """一句话描述函数功能。
    
    Args:
        param1: 参数1描述
        param2: 参数2描述
        
    Returns:
        返回值描述
        
    Raises:
        ValueError: 当参数无效时
    """
    pass
```

---

## 工具配置

### Ruff

```toml
# pyproject.toml
[tool.ruff]
line-length = 88
target-version = "py38"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "N", "UP", "B"]
```

### Pytest

```toml
# pyproject.toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_functions = ["test_*"]
```

---

*本规则适用于 Python 项目的 AI Agent 开发。*
