# Python 语言规则

> 适用于 Python

---

## 代码风格
 | 规范 | 示例 |
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

## AI

> 以下是 AI 生成代码中最常见的问题，validate_language_rules.py 会自动检测

### 反模式 1: 裸 except

```python
# ❌ 反模式: bare except
try:
    result = api.call()
except:
    pass

# ✅ 正确: 指定异常类型
try:
    result = api.call()
except ConnectionError as e:
    logger.error(f"API connection failed: {e}")
    raise
```

### 反模式 2: 可变默认参数

```python
# ❌ 反模式: mutable default
def add_item(item, items=[]):
    items.append(item)
    return items


# ✅ 正确: use None as default
def add_item(item, items=None):
    if items is None:
        items = []
    items.append(item)
    return items
```

### 反模式 3: eval/exec

```python
# ❌ 反模式: eval
result = eval(user_input)

# ✅ 正确: safe alternatives
result = ast.literal_eval(user_input)  # for data
```

### 反模式 4: SQL 字符串拼接

```python
# ❌ 反模式: SQL injection
cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")

# ✅ 正确: parameterized query
cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
```

### 反模式 5: print 作为日志

```python
# ❌ 反模式: print in production
print(f"Processing {item}")

# ✅ 正确: use logging
logger.info(f"Processing {item}")
```

### 反模式 6: 通配符导入

```python
# ❌ 反模式: wildcard import
from module import *

# ✅ 正确: explicit imports
from module import function1, function2
```

### 反模式 7: 测试中的 sleep

```python
# ❌ 反模式: time.sleep in tests
def test_api():
    result = call_api()
    time.sleep(5)
    assert result.status == 200


# ✅ 正确: polling with timeout
def test_api():
    result = poll_until(lambda: call_api().status == 200, timeout=5)
    assert result.status == 200
```

---

## 量化阈值

| 指标 | 阈值 | 说明 |
|------|------|------|
| 函数最大行数 | 50 | 超过应拆分 |
| 文件最大行数 | 500 | 超过应模块化 |
| 行最大长度 | 120 | 超过应换行 |
| 最大嵌套深度 | 4 | 超过应提取函数 |
| 最大函数参数 | 7 | 超过应使用 dataclass |
| 最大圈复杂度 | 10 | 超过应简化逻辑 |
| | 80% | CI 门禁要求 |

---

*本规则适用于 Python 项目的 AI Agent 开发。*
*验证工具: `python tools/scripts/validate_language_rules.py <path> --lang python`*
