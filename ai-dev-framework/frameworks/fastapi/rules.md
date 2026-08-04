# FastAPI 开发规则

> 基于 Python 3.10+ 的 FastAPI 开发标准

---

## 核心约定

### 文件组织

```
app/
├── api/
│   ├── v1/
│   │   ├── endpoints/    # 路由处理
│   │   ├── __init__.py
│   │   └── router.py     # 路由聚合
│   └── deps.py           # 依赖注入
├── core/
│   ├── config.py         # 应用配置
│   ├── security.py       # 安全配置
│   └── database.py       # 数据库连接
├── models/               # SQLAlchemy/SQLModel 模型
├── schemas/              # Pydantic 模型
├── services/             # 业务逻辑
└── main.py              # 入口
```

### 命名规范

- **文件**: `snake_case.py`
- **类**: `PascalCase` (UserService)
- **函数**: `snake_case` (get_current_user)
- **路由函数**: `snake_case`
- **Pydantic 模型**: `PascalCase` (CreateUserRequest)

---

## API 规范

```python
# ✅ 推荐的 API 结构
from fastapi import APIRouter, Depends, HTTPException, status
from app.schemas.user import UserCreate, UserResponse
from app.services.user import UserService
from app.api.deps import get_current_user

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/", response_model=list[UserResponse])
async def list_users(
    skip: int = 0,
    limit: int = 100,
    service: UserService = Depends(get_user_service),
    current_user: User = Depends(get_current_user),
):
    """获取用户列表"""
    return await service.list(skip=skip, limit=limit)


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    data: UserCreate,
    service: UserService = Depends(get_user_service),
):
    """创建用户"""
    return await service.create(data)
```

---

## 质量门禁

### Lint

```bash
# 检查
ruff check app/
mypy app/

# 格式化
ruff format --check app/
```

### 测试

```bash
# 测试
pytest app/tests/ -v --cov=app
```

---

## 依赖注入

```python
# ✅ 清晰的依赖注入
from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

async def get_db() -> AsyncSession:
    async with async_session() as session:
        yield session

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """获取当前用户"""
    user = await user_service.get_by_token(db, token)
    if not user:
        raise HTTPException(status_code=401)
    return user
```

---

## 常用依赖

| 用途 | 推荐包 |
|------|--------|
| ORM | SQLAlchemy 2.0 / SQLModel |
| 迁移 | Alembic |
| 数据校验 | Pydantic v2 |
| 认证 | python-jose + passlib |
| 测试 | pytest + httpx |
| 异步 | asyncpg + aiohttp |
