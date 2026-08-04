---
title: SQL Governance Rules
description: "> 适用于: SQL 项目 (PostgreSQL, MySQL, SQLite, SQ..."
category: 治理层
tags: ['测试', 'AI', 'SQL']
difficulty: 基础
reading_time: 10 分钟
updated: 2026-07-21
---

# SQL Governance Rules

> 适用于: SQL 项目 (PostgreSQL, MySQL, SQLite, SQL Server)

---

## 1. 代码规范

### 格式化

```bash
# 使用 sql-formatter
npx sql-formatter --config .sqlformrc "**/*.sql"

# 或使用 pgFormatter (PostgreSQL)
pg_format *.sql
```

### 命名规范

```sql
-- ✅ 正确 - 使用 snake_case
CREATE TABLE user_profiles (
    user_id INTEGER PRIMARY KEY,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ✅ 正确 - 使用 PascalCase (仅限存储过程)
CREATE PROCEDURE GetUserProfile(
    @UserId INTEGER
)
AS
BEGIN
    SELECT * FROM user_profiles WHERE user_id = @UserId;
END;

-- ❌ 禁止
CREATE TABLE UserProfiles (  -- 应使用 snake_case
    UserId INTEGER PRIMARY KEY,  -- 应使用 snake_case
    FirstName VARCHAR(100) NOT NULL  -- 应使用 snake_case
);
```

---

## 2. 查询优化

### 索引使用

```sql
-- ✅ 正确 - 在 WHERE 和 JOIN 条件上创建索引
CREATE INDEX idx_user_profiles_email ON user_profiles(email);
CREATE INDEX idx_orders_user_id ON orders(user_id);

-- ✅ 正确 - 使用复合索引
CREATE INDEX idx_orders_user_status ON orders(user_id, status);

-- ❌ 禁止 - 在低基数列上创建索引
CREATE INDEX idx_users_gender ON users(gender); -- 性别只有几个值
```

### 查询性能

```sql
-- ✅ 正确 - 使用 EXPLAIN 分析查询
EXPLAIN ANALYZE
SELECT * FROM orders WHERE user_id = 123;

-- ✅ 正确 - 避免 SELECT *
SELECT user_id, first_name, last_name
FROM user_profiles
WHERE user_id = 123;

-- ❌ 禁止
SELECT * FROM user_profiles;  -- 返回所有列
SELECT * FROM orders WHERE YEAR(created_at) = 2026;  -- 函数阻止索引使用
```

---

## 3. 数据完整性

### 约束

```sql
-- ✅ 正确 - 使用外键约束
CREATE TABLE orders (
    order_id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    total DECIMAL(10, 2) NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

-- ✅ 正确 - 使用 CHECK 约束
CREATE TABLE products (
    product_id SERIAL PRIMARY KEY,
    price DECIMAL(10, 2) NOT NULL CHECK (price > 0),
    stock INTEGER NOT NULL CHECK (stock >= 0)
);

-- ❌ 禁止 - 缺少约束
CREATE TABLE orders (
    order_id INTEGER,
    user_id INTEGER,
    total DECIMAL(10, 2)
);
```

### 事务

```sql
-- ✅ 正确 - 使用事务
BEGIN TRANSACTION;

UPDATE accounts SET balance = balance - 100 WHERE account_id = 1;
UPDATE accounts SET balance = balance + 100 WHERE account_id = 2;

COMMIT;

-- ✅ 正确 - 使用保存点
BEGIN TRANSACTION;

SAVEPOINT before_update;
UPDATE accounts SET balance = balance - 100 WHERE account_id = 1;

IF (SELECT balance FROM accounts WHERE account_id = 1) < 0 THEN
    ROLLBACK TO before_update;
END IF;

COMMIT;
```

---

## 4. 安全性

### SQL 注入防护

```sql
-- ✅ 正确 - 使用参数化查询
PREPARE stmt FROM 'SELECT * FROM users WHERE email = ?';
SET @email = 'user@example.com';
EXECUTE stmt USING @email;

-- ❌ 禁止 - 直接拼接用户输入
SET @query = CONCAT('SELECT * FROM users WHERE email = "', @user_input, '"');
PREPARE stmt FROM @query;
EXECUTE stmt;
```

### 权限管理

```sql
-- ✅ 正确 - 最小权限原则
CREATE USER 'app_user'@'localhost' IDENTIFIED BY 'password';
GRANT SELECT, INSERT, UPDATE ON mydb.* TO 'app_user'@'localhost';

-- ❌ 禁止 - 使用 root 用户
GRANT ALL PRIVILEGES ON *.* TO 'app_user'@'localhost';
```

---

## 5. 存储过程

### 错误处理

```sql
-- ✅ 正确 - 使用异常处理
CREATE PROCEDURE TransferFunds(
    @from_account INTEGER,
    @to_account INTEGER,
    @amount DECIMAL(10, 2)
)
AS
BEGIN
    BEGIN TRY
        BEGIN TRANSACTION;
        
        UPDATE accounts SET balance = balance - @amount WHERE account_id = @from_account;
        UPDATE accounts SET balance = balance + @amount WHERE account_id = @to_account;
        
        IF @@ROWCOUNT = 0
        BEGIN
            RAISERROR('Account not found', 16, 1);
        END
        
        COMMIT;
    END TRY
    BEGIN CATCH
        ROLLBACK;
        THROW;
    END CATCH
END;
```

---

## 6. 测试

```sql
-- ✅ 正确 - 使用测试数据
-- test_data.sql
INSERT INTO users (user_id, email, name) VALUES
(1, 'test@example.com', 'Test User'),
(2, 'admin@example.com', 'Admin User');

-- test_queries.sql
-- 测试用户查询
SELECT * FROM user_profiles WHERE user_id = 1;
-- 预期: 返回 Test User 的资料
```

---

## 7. 文档

```sql
-- ✅ 正确 - 添加注释
-- 用户资料表
-- 存储用户的基本信息
CREATE TABLE user_profiles (
    user_id INTEGER PRIMARY KEY,  -- 用户唯一标识
    email VARCHAR(255) NOT NULL UNIQUE,  -- 用户邮箱
    first_name VARCHAR(100) NOT NULL,  -- 名
    last_name VARCHAR(100) NOT NULL,  -- 姓
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP  -- 创建时间
);

-- ❌ 禁止 - 缺少注释
CREATE TABLE user_profiles (
    user_id INTEGER PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 8. 禁止行为

| 行为 | 原因 |
|------|------|
| 使用 `SELECT *` | 只选择需要的列 |
| 使用隐式类型转换 | 使用显式 CAST |
| 使用 `!=` | 使用 `<>` |
| 使用 `HAVING` 代替 `WHERE` | 先过滤再聚合 |
| 使用 `OR` 代替 `IN` | `IN` 更清晰 |
| 使用 `NOT IN` 与 NULL | 使用 `NOT EXISTS` |

---

*最后更新: 2026-07-21*
