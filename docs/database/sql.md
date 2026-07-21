---
title: SQL Governance Rules
description: > 适用于 SQL 数据库的 AI Agent 开发规范。
category: 工具层
tags: ['测试', 'AI', 'SQL', 'Python']
difficulty: 初级
reading_time: 10 分钟
updated: 2026-07-21
---

# SQL Governance Rules

> 适用于 SQL 数据库的 AI Agent 开发规范。

---

## 1. 数据库设计

### 范式化

```sql
-- ✅ 正确: 第三范式 (3NF)
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE posts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    author_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    content TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ❌ 禁止: 反范式化 (除非有性能理由)
CREATE TABLE posts_denormalized (
    id UUID PRIMARY KEY,
    author_email VARCHAR(255),  -- 冗余存储
    author_name VARCHAR(255),   -- 冗余存储
    title VARCHAR(255)
);
```

### 索引设计

```sql
-- ✅ 正确: 为常用查询创建索引
CREATE INDEX idx_posts_author_id ON posts(author_id);
CREATE INDEX idx_posts_created_at ON posts(created_at DESC);
CREATE INDEX idx_users_email ON users(email);

-- ✅ 正确: 复合索引
CREATE INDEX idx_posts_author_created ON posts(author_id, created_at DESC);

-- ❌ 禁止: 过度索引
CREATE INDEX idx_users_name ON users(name);  -- 很少查询
CREATE INDEX idx_users_created_at ON users(created_at);  -- 很少查询
```

---

## 2. 查询优化

### 使用 EXPLAIN

```sql
-- ✅ 正确: 分析查询计划
EXPLAIN ANALYZE
SELECT * FROM posts WHERE author_id = '123' ORDER BY created_at DESC LIMIT 10;

-- ❌ 禁止: 不分析就优化
SELECT * FROM posts WHERE author_id = '123' ORDER BY created_at DESC LIMIT 10;
```

### 避免 SELECT *

```sql
-- ❌ 禁止: SELECT *
SELECT * FROM users WHERE id = '123';

-- ✅ 正确: 只选择需要的列
SELECT id, email, name FROM users WHERE id = '123';
```

### 分页优化

```sql
-- ❌ 禁止: OFFSET 分页 (大偏移量性能差)
SELECT * FROM posts ORDER BY created_at DESC OFFSET 10000 LIMIT 10;

-- ✅ 正确: 游标分页
SELECT * FROM posts 
WHERE created_at < '2024-01-01' 
ORDER BY created_at DESC 
LIMIT 10;
```

---

## 3. 事务管理

### 事务使用

```sql
-- ✅ 正确: 事务保护
BEGIN;
UPDATE accounts SET balance = balance - 100 WHERE id = 'user1';
UPDATE accounts SET balance = balance + 100 WHERE id = 'user2';
COMMIT;

-- ❌ 禁止: 部分更新
UPDATE accounts SET balance = balance - 100 WHERE id = 'user1';
-- 如果这里失败，数据不一致
UPDATE accounts SET balance = balance + 100 WHERE id = 'user2';
```

### 隔离级别

```sql
-- ✅ 正确: 设置合适的隔离级别
SET TRANSACTION ISOLATION LEVEL READ COMMITTED;

-- 或在连接级别设置
SET default_transaction_isolation = 'read committed';
```

---

## 4. 安全规范

### SQL 注入防护

```sql
-- ❌ 禁止: 字符串拼接
SELECT * FROM users WHERE id = '${userId}';

-- ✅ 正确: 使用参数化查询
PREPARE stmt FROM 'SELECT * FROM users WHERE id = ?';
EXECUTE stmt USING @userId;
```

### 权限管理

```sql
-- ✅ 正确: 最小权限
CREATE USER 'app_user'@'localhost' IDENTIFIED BY 'password';
GRANT SELECT, INSERT, UPDATE ON mydb.users TO 'app_user'@'localhost';
GRANT SELECT, INSERT, UPDATE ON mydb.posts TO 'app_user'@'localhost';

-- ❌ 禁止: 使用 root
CREATE USER 'root'@'%' IDENTIFIED BY 'password';  -- 不安全
```

---

## 5. 迁移规范

### 版本化迁移

```sql
-- ✅ 正确: 增量迁移
-- V1__create_users.sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL
);

-- V2__add_user_name.sql
ALTER TABLE users ADD COLUMN name VARCHAR(255) NOT NULL DEFAULT '';

-- ❌ 禁止: 直接修改生产数据库
ALTER TABLE users ADD COLUMN new_field TEXT;  -- 无版本控制
```

### 回滚策略

```sql
-- ✅ 正确: 每个迁移都有回滚
-- V2__add_user_name.sql
ALTER TABLE users ADD COLUMN name VARCHAR(255) NOT NULL DEFAULT '';

-- V2__rollback.sql
ALTER TABLE users DROP COLUMN name;
```

---

## 6. 测试规范

### 测试数据库

```python
# ✅ 正确: 使用测试数据库
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

@pytest.fixture
def db_session():
    engine = create_engine('postgresql://localhost/test_db')
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.rollback()
    session.close()
```

### 数据清理

```python
# ✅ 正确: 每个测试后清理数据
@pytest.fixture(autouse=True)
def clean_db(db_session):
    yield
    db_session.rollback()
    for table in reversed(Base.metadata.sorted_tables):
        db_session.execute(table.delete())
    db_session.commit()
```

---

## 7. 质量检查清单

### 设计

- [ ] 范式化设计
- [ ] 合理的索引
- [ ] 主键和外键约束
- [ ] 数据类型选择正确

### 查询

- [ ] 使用 EXPLAIN 分析
- [ ] 避免 SELECT *
- [ ] 优化分页查询
- [ ] 避免 N+1 查询

### 安全

- [ ] 参数化查询
- [ ] 最小权限
- [ ] 敏感数据加密
- [ ] 审计日志

---

*本规范随 SQL 数据库演进持续更新。最后更新: 2026-07-17*
