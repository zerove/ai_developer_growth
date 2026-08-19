---
title: Python Governance Rules
description: > 适用于 Python 项目的 AI Agent 开发规范。
category: 治理层
tags: ['AI', 'API', 'Python', '测试', 'SQL']
difficulty: 高级
reading_time: 10 分钟
updated: 2026-07-21
---

# Python Governance Rules

> 适用于 Python 项目的 AI Agent 开发规范。

---

## 1. 代码规范

### 格式化

- **工具**: `ruff format` 或 `black`
- **行宽**: 88 字符
- **引号**: 双引号
- **缩进**: 4 空格

### Linting

- **工具**: `ruff check` 或 `flake8`
- **规则**: 启用 `E`, `F`, `W` 规则集
- **类型检查**: `mypy` 或 `pyright`

### 导入排序

```python
# 标准库
import os
import sys
from pathlib import Path

# 第三方库
import requests
from fastapi import FastAPI

# 本地模块
from .models import User
from .utils import helper
```

---

## 2. 错误处理

### 自定义异常

```python
class AppError(Exception):
    """应用基础异常"""

    pass


class ValidationError(AppError):
    """验证错误"""

    def __init__(self, field: str, message: str):
        self.field = field
        self.message = message
        super().__init__(f"Validation error on {field}: {message}")


class NotFoundError(AppError):
    """资源不存在"""

    def __init__(self, resource: str, id: str):
        self.resource = resource
        self.id = id
        super().__init__(f"{resource} with id {id} not found")
```

### 禁止行为

```python
# ❌ 禁止
def get_user(id: str) -> User:
    return db.query(User).filter(User.id == id).one()  # 可能抛出异常


# ❌ 禁止
try:
    do_something()
except:
    pass  # 空 catch


# ✅ 正确
def get_user(id: str) -> User:
    try:
        user = db.query(User).filter(User.id == id).one()
        return user
    except NoResultFound:
        raise NotFoundError("User", id)
```

---

## 3. 类型安全

### 类型注解

```python
# ❌ 禁止
def process(data):
    return data["key"]


# ✅ 正确
from typing import Any


def process(data: dict[str, Any]) -> str:
    return data.get("key", "")
```

### 泛型

```python
from typing import TypeVar, Generic

T = TypeVar("T")


class Repository(Generic[T]):
    def __init__(self, session: Session):
        self.session = session

    def get(self, id: str) -> T: ...

    def create(self, entity: T) -> T: ...
```

---

## 4. 异步编程

### async/await

```python
import asyncio
from typing import AsyncGenerator


# ✅ 正确
async def fetch_data(url: str) -> dict:
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.json()


# ✅ 正确
async def process_items(items: list[str]) -> AsyncGenerator[str, None]:
    for item in items:
        result = await process(item)
        yield result
```

### 禁止行为

```python
# ❌ 禁止: 在 async 函数中使用同步 IO
async def bad_example():
    with open("file.txt") as f:  # 阻塞!
        return f.read()


# ✅ 正确
async def good_example():
    async with aiofiles.open("file.txt") as f:
        return await f.read()
```

---

## 5. 测试规范

### pytest 结构

```python
import pytest
from unittest.mock import AsyncMock, patch


class TestUserService:
    """用户服务测试"""

    @pytest.fixture
    def service(self):
        return UserService()

    @pytest.mark.asyncio
    async def test_get_user_found(self, service):
        """测试获取用户 - 存在"""
        user = await service.get_user("123")
        assert user.id == "123"

    @pytest.mark.asyncio
    async def test_get_user_not_found(self, service):
        """测试获取用户 - 不存在"""
        with pytest.raises(NotFoundError):
            await service.get_user("nonexistent")
```

### Mock 规范

```python
# ✅ 正确: 使用 AsyncMock
@patch("app.services.db")
async def test_with_mock(mock_db):
    mock_db.query.return_value = AsyncMock()
    result = await service.get_user("123")
    assert result is not None


# ❌ 禁止: 手动创建 mock
class MockDB:
    def query(self, model):
        return self

    def filter(self, condition):
        return self

    def one(self):
        return None
```

---

## 6. 项目结构

```
project/
├── src/
│   ├── __init__.py
│   ├── main.py
│   ├── models/
│   ├── services/
│   ├── repositories/
│   └── utils/
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   └── test_*.py
├── pyproject.toml
└── README.md
```

### 依赖管理

- **工具**: `poetry` 或 `uv`
- **锁定**: 使用 `poetry.lock` 或 `uv.lock`
- **虚拟环境**: 每个项目独立虚拟环境

---

## 7. 性能优化

### 缓存

```python
from functools import lru_cache


@lru_cache(maxsize=128)
def expensive_calculation(n: int) -> int:
    # 耗时计算
    return n * n
```

### 批量操作

```python
# ❌ 禁止: 逐条插入
for item in items:
    db.add(item)
db.commit()

# ✅ 正确: 批量插入
db.bulk_save_objects(items)
db.commit()
```

---

## 8. 安全规范

### SQL 注入防护

```python
# ❌ 禁止: 字符串拼接
query = f"SELECT * FROM users WHERE id = {user_id}"

# ✅ 正确: 参数化查询
query = "SELECT * FROM users WHERE id = :user_id"
result = db.execute(text(query), {"user_id": user_id})
```

### 密钥管理

```python
import os

# ❌ 禁止
API_KEY = "YOUR_API_KEY_HERE"

# ✅ 正确
API_KEY = os.getenv("API_KEY")
if not API_KEY:
    raise ValueError("API_KEY environment variable not set")
```

---

## 9. 日志规范

```python
import logging

logger = logging.getLogger(__name__)


# ✅ 正确
def process_user(user_id: str):
    logger.info("Processing user %s", user_id)
    try:
        # 处理逻辑
        logger.info("Successfully processed user %s", user_id)
    except Exception as e:
        logger.error("Failed to process user %s: %s", user_id, e)
        raise
```

### 禁止行为

```python
# ❌ 禁止: 打印敏感信息
print(f"Processing user {user_id} with token {api_key}")

# ❌ 禁止: 使用 print 代替 logger
print(f"Error: {e}")
```

---

## 10. 质量检查清单

### 代码质量

- [ ] `ruff format` 通过
- [ ] `ruff check` 无错误
- [ ] `mypy` 无类型错误
- [ ] 无 `unwrap()`/`expect()` 等价物
- [ ] 无硬编码密钥

### 测试质量

- [ ] 核心逻辑测试覆盖 > 80%
- [ ] 所有测试通过
- [ ] 无空 except 块
- [ ] Mock 使用正确

### 文档质量

- [ ] 函数有 docstring
- [ ] 类有 docstring
- [ ] 复杂逻辑有注释
- [ ] README.md 已更新

---

*本规范随 Python 生态演进持续更新。最后更新: 2026-07-17*
