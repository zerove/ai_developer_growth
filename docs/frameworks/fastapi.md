---
title: FastAPI Governance Rules
description: > 适用于 FastAPI 项目的 AI Agent 开发规范。
category: 工具层
tags: ['AI', 'API', 'Python', '测试', 'SQL']
difficulty: 基础
reading_time: 10 分钟
updated: 2026-07-21
---

# FastAPI Governance Rules

> 适用于 FastAPI 项目的 AI Agent 开发规范。

---

## 1. 项目结构

### 应用组织

```
project/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── api/
│   │   ├── deps.py
│   │   └── v1/
│   │       ├── endpoints/
│   │       └── router.py
│   ├── core/
│   │   ├── config.py
│   │   └── security.py
│   ├── models/
│   ├── schemas/
│   ├── services/
│   └── repositories/
├── tests/
├── pyproject.toml
└── README.md
```

---

## 2. 路由规范

### 路由组织

```python
from fastapi import APIRouter, Depends, HTTPException
from app.schemas.user import UserCreate, UserResponse
from app.services.user import UserService

router = APIRouter(prefix="/users", tags=["users"])


# ✅ 正确
@router.get("/", response_model=list[UserResponse])
async def list_users(
    service: UserService = Depends(get_user_service),
):
    return await service.get_all()


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    service: UserService = Depends(get_user_service),
):
    user = await service.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user
```

### 路由分组

```python
# ✅ 正确: 使用 APIRouter
from fastapi import APIRouter

api_router = APIRouter()
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(posts.router, prefix="/posts", tags=["posts"])

# main.py
app.include_router(api_router, prefix="/api/v1")
```

---

## 3. Pydantic 模型

### 请求/响应模型

```python
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime


# ✅ 正确
class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    name: str = Field(..., min_length=1, max_length=100)


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    created_at: datetime

    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    name: str | None = Field(None, min_length=1, max_length=100)
```

### 禁止行为

```python
# ❌ 禁止: 无验证
class UserCreate(BaseModel):
    email: str  # 应使用 EmailStr
    password: str  # 应指定 min_length


# ❌ 禁止: 手动转换
def create_user(data: dict):
    return User(**data)  # 应使用 Pydantic 验证
```

---

## 4. 依赖注入

### 依赖项

```python
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession


# ✅ 正确
async def get_db() -> AsyncSession:
    async with async_session() as session:
        yield session


async def get_user_service(
    db: AsyncSession = Depends(get_db),
) -> UserService:
    return UserService(db)


# 路由中使用
@router.get("/")
async def list_users(
    service: UserService = Depends(get_user_service),
):
    return await service.get_all()
```

### 认证依赖

```python
from fastapi import Security
from fastapi.security import HTTPBearer

security = HTTPBearer()


async def get_current_user(
    token: str = Security(security),
) -> User:
    user = await verify_token(token.credentials)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user


# 路由中使用
@router.get("/me")
async def get_me(user: User = Depends(get_current_user)):
    return user
```

---

## 5. 异步编程

### 异步视图

```python
# ✅ 正确
@router.get("/")
async def list_users():
    users = await db.fetch_all()
    return users


# ❌ 禁止: 同步阻塞
@router.get("/")
def list_users():
    users = db.fetch_all()  # 阻塞!
    return users
```

### 异步数据库操作

```python
from sqlalchemy.ext.asyncio import AsyncSession


# ✅ 正确
async def get_user(db: AsyncSession, user_id: str) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()
```

---

## 6. 测试规范

### Pytest + AsyncIO

```python
import pytest
from httpx import AsyncClient
from app.main import app


@pytest.mark.asyncio
async def test_list_users():
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/v1/users/")
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_create_user():
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/users/",
            json={"email": "test@example.com", "password": "testpass123"},
        )
        assert response.status_code == 201
```

### Mock 模块

```python
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_get_user():
    with patch("app.services.user.UserService.get_by_id") as mock:
        mock.return_value = User(id="1", email="test@example.com")

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/api/v1/users/1")
            assert response.status_code == 200
```

---

## 7. 安全规范

### CORS 配置

```python
from fastapi.middleware.cors import CORSMiddleware

# ✅ 正确
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://example.com"],  # 限制来源
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
```

### 密钥管理

```python
# ❌ 禁止
SECRET_KEY = "YOUR_API_KEY_HERE"

# ✅ 正确
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    secret_key: str
    database_url: str

    class Config:
        env_file = ".env"


settings = Settings()
```

---

## 8. 质量检查清单

### 代码质量

- [ ] Black 格式化通过
- [ ] Ruff 无错误
- [ ] 类型注解完整
- [ ] 无硬编码密钥
- [ ] 使用 Pydantic 模型

### 测试质量

- [ ] 核心 API 测试覆盖 > 80%
- [ ] 所有测试通过
- [ ] 异步测试使用 pytest-asyncio
- [ ] Mock 使用正确

### 安全

- [ ] CORS 配置正确
- [ ] 认证依赖完整
- [ ] 输入验证完整

---

*本规范随 FastAPI 生态演进持续更新。最后更新: 2026-07-17*
