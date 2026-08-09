---
title: ORM 最佳实践
description: "> SQLAlchemy (Python)、Prisma (TypeScript)、GO..."
category: 工具层
tags: ['AI', 'REST', 'Python', 'SQL', 'TypeScript']
difficulty: 基础
reading_time: 10 分钟
updated: 2026-07-21
---

# ORM 最佳实践

> SQLAlchemy (Python)、Prisma (TypeScript)、GORM (Go)、Django ORM 通用原则与避坑指南。

---

## 1. 核心原则

| 原则 | 说明 | 反例 |
|------|------|------|
| **显式优于隐式** | 查询、加载策略、事务边界全显式 | `User.posts` 隐式触发 N+1 |
| **单一职责** | Repository 封装查询，Service 编排业务 | Service 里写原生 SQL |
| **不可变实体** | Entity 只读，变更通过方法 | 直接 `user.name = "x"` 无验证 |
| **乐观锁默认开启** | 版本号/时间戳防并发丢失更新 | 无版本字段，并发覆盖 |
| **连接池配置即代码** | Pool size、timeout、recycle 纳入配置 | 使用默认值导致生产爆连接 |

---

## 2. SQLAlchemy (Python) 实战模式

### 2.1 模型定义规范
```python
# models/user.py
from sqlalchemy import Column, Integer, String, DateTime, func, Index
from sqlalchemy.orm import declarative_base, relationship, declared_attr
from sqlalchemy.ext.hybrid import hybrid_property

Base = declarative_base()

class TimestampMixin:
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

class VersionMixin:
    version = Column(Integer, default=1, nullable=False)  # 乐观锁

class User(Base, TimestampMixin, VersionMixin):
    __tablename__ = "users"
    __table_args__ = (
        Index("ix_users_email_active", "email", "is_active"),
        {"comment": "用户表"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(100))
    is_active = Column(Boolean, default=True, nullable=False)

    # 关系：显式 lazy="selectin" 避免 N+1
    posts = relationship("Post", back_populates="author", lazy="selectin")
    orders = relationship("Order", back_populates="user", lazy="raise")  # 强制显式加载

    @hybrid_property
    def post_count(self):
        return len(self.posts)

    @post_count.expression
    def post_count(cls):
        return select(func.count(Post.id)).where(Post.author_id == cls.id)
```

### 2.2 Repository 模式
```python
# repositories/user_repo.py
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from typing import Optional, List

class UserRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_by_id(self, user_id: int, *, load_posts: bool = False) -> Optional[User]:
        stmt = select(User).where(User.id == user_id)
        if load_posts:
            stmt = stmt.options(selectinload(User.posts))
        return self.session.execute(stmt).scalar_one_or_none()

    def get_by_email(self, email: str) -> Optional[User]:
        return self.session.execute(
            select(User).where(User.email == email)
        ).scalar_one_or_none()

    def list_active(self, *, limit: int = 50, offset: int = 0) -> List[User]:
        return self.session.execute(
            select(User)
            .where(User.is_active == True)
            .order_by(User.created_at.desc())
            .limit(limit)
            .offset(offset)
        ).scalars().all()

    def create(self, user: User) -> User:
        self.session.add(user)
        self.session.flush()  # 获取 ID，不提交
        return user

    def update_optimistic(self, user: User, expected_version: int) -> bool:
        """乐观锁更新，版本不匹配返回 False"""
        result = self.session.execute(
            update(User)
            .where(User.id == user.id, User.version == expected_version)
            .values(
                full_name=user.full_name,
                is_active=user.is_active,
                version=User.version + 1,
                updated_at=func.now(),
            )
        )
        return result.rowcount > 0
```

### 2.3 事务边界
```python
# services/user_service.py
from contextlib import contextmanager

class UserService:
    def __init__(self, session_factory: sessionmaker):
        self.session_factory = session_factory

    @contextmanager
    def transaction(self):
        session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def register_user(self, email: str, password: str) -> User:
        with self.transaction() as session:
            repo = UserRepository(session)
            if repo.get_by_email(email):
                raise ValueError("Email already registered")

            user = User(
                email=email,
                hashed_password=hash_password(password),
            )
            return repo.create(user)

    def change_email(self, user_id: int, new_email: str) -> User:
        with self.transaction() as session:
            repo = UserRepository(session)
            user = repo.get_by_id(user_id)
            if not user:
                raise NotFoundError("User")

            if repo.get_by_email(new_email):
                raise ValueError("Email taken")

            user.email = new_email
            # version 自动增
            return user
```

### 2.4 常见坑与修正

| 坑 | 症状 | 修正 |
|----|------|------|
| **N+1 查询** | 列表页查 100 条发 101 条 SQL | `selectinload` / `joinedload` 显式预加载 |
| **事务过长** | 连接池耗尽、锁竞争 | 业务逻辑移出事务，仅持久化在事务内 |
| **Detached Instance** | 访问关系属性报错 | 显式 `selectinload` 或 `session.merge()` |
| **脏读/幻读** | 并发下数据不一致 | 乐观锁 `version` + `REPEATABLE READ` 隔离级 |
| **大对象加载** | 内存爆炸 | `yield_per(100)` 分批、只选需要列 `load_only()` |

---

## 3. Prisma (TypeScript) 要点

```typescript
// prisma/schema.prisma
model User {
  id        Int      @id @default(autoincrement())
  email     String   @unique
  password  String
  name      String?
  version   Int      @default(1)  // 乐观锁
  createdAt DateTime @default(now())
  updatedAt DateTime @updatedAt
  posts     Post[]
  @@index([email, isActive])
}

// 乐观锁中间件
// prisma/extensions/optimistic-lock.ts
import { PrismaClient, Prisma } from '@prisma/client'

export const optimisticLockExtension = Prisma.defineExtension({
  name: 'optimisticLock',
  model: {
    $allModels: {
      async update<T, Args>(this: T, args: Prisma.Args<T, 'update'>) {
        const { where, data, ...rest } = args
        return this.$transaction(async (tx) => {
          const current = await (tx as any)[this.modelName].findUnique({ where })
          if (!current) throw new Error('Not found')
          if (current.version !== data.version) {
            throw new Error('OPTIMISTIC_LOCK_FAILED')
          }
          data.version = current.version + 1
          return (tx as any)[this.modelName].update({ where, data, ...rest })
        })
      },
    },
  },
})

// 使用
const prisma = new PrismaClient().$extends(optimisticLockExtension)
await prisma.user.update({
  where: { id: 1 },
  data: { name: 'New', version: 1 }, // 必须传当前版本
})
```

---

## 4. GORM (Go) 关键配置

```go
// config/database.go
func NewDB(cfg Config) (*gorm.DB, error) {
    dsn := fmt.Sprintf("host=%s user=%s password=%s dbname=%s port=%s sslmode=disable",
        cfg.Host, cfg.User, cfg.Password, cfg.Name, cfg.Port)

    db, err := gorm.Open(postgres.Open(dsn), &gorm.Config{
        PrepareStmt:            true,           // 预编译缓存
        SkipDefaultTransaction: true,           // 手动控制事务
        Logger:                 logger.Default.LogMode(logger.Warn),
    })
    if err != nil {
        return nil, err
    }

    sqlDB, _ := db.DB()
    sqlDB.SetMaxOpenConns(cfg.MaxOpenConns)      // 如 20
    sqlDB.SetMaxIdleConns(cfg.MaxIdleConns)      // 如 10
    sqlDB.SetConnMaxLifetime(time.Hour)          // 连接回收
    sqlDB.SetConnMaxIdleTime(30 * time.Minute)

    // 自动迁移（仅开发/测试）
    if cfg.AutoMigrate {
        db.AutoMigrate(&User{}, &Post{})
    }
    return db, nil
}

// 乐观锁
type BaseModel struct {
    ID        uint           `gorm:"primarykey"`
    CreatedAt time.Time
    UpdatedAt time.Time
    DeletedAt gorm.DeletedAt `gorm:"index"`
    Version   int            `gorm:"default:1"`
}

func (b *BaseModel) BeforeUpdate(tx *gorm.DB) error {
    if b.Version == 0 {
        return errors.New("version required for update")
    }
    tx.Statement.SetColumn("version", b.Version+1)
    return nil
}
```

---

## 5. 通用性能清单

| 场景 | 推荐做法 |
|------|----------|
| **列表分页** | Keyset Pagination (`WHERE id > last_id ORDER BY id LIMIT 20`) 而非 `OFFSET` |
| **批量插入** | `INSERT ... ON CONFLICT` / `bulk_insert_mappings` / `CreateInBatches(100)` |
| **只读查询** | `AsNoTracking()` (EF) / `Session(expire_on_commit=False)` / `ReadUncommitted` |
| **大字段** | `defer` / `load_only` / 单独表存储 (LOB) |
| **计数** | `COUNT(*)` 慢 → 缓存计数 / 触发器维护计数列 / 近似 `pg_estimate` |
| **连接池** | `max_open = CPU * 2`、`max_idle = max_open / 2`、`max_lifetime < 防火墙超时` |

---

## 6. 迁移策略见 [database/migration.md](migration.md)

---

*ORM 是工具，SQL 是底层能力。最后更新: 2026-07-20*
