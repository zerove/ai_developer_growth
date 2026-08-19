---
title: AI 辅助数据库设计
description: 使用 AI 工具设计数据库模型
category: 效率层
tags: [AI, 数据库, 数据建模]
difficulty: 进阶
reading_time: 10 分钟
updated: 2026-07-21
---

# AI 辅助数据库设计

## 核心原则

AI 数据库设计 = 业务分析 + 数据建模 + 优化建议

## 设计流程

```
需求分析 → 概念设计 → 逻辑设计 → 物理设计 → 优化
```

## Prompt 技巧

### 1. 需求分析

```markdown
请分析数据需求:
- 业务实体: 用户、订单、商品
- 实体关系: 用户-订单 (1:N)，订单-商品 (M:N)
- 数据量: 用户 100 万，订单 1000 万
- 查询模式: 按用户查订单，按时间查订单
```

### 2. 模型生成

```markdown
请生成数据库模型:
- 用户表: id, name, email, created_at
- 订单表: id, user_id, amount, status, created_at
- 商品表: id, name, price
- 订单商品表: order_id, product_id, quantity
```

### 3. 优化建议

```markdown
请优化数据库设计:
- 索引设计
- 分区策略
- 查询优化
```

## 设计模式

### 1. 范式设计

**第三范式 (3NF):**
```
消除传递依赖
每个非主属性完全依赖于主键
每个非主属性不传递依赖于主键
```

**适用:**
- OLTP 系统
- 写密集场景
- 数据一致性要求高

### 2. 反范式设计

**冗余策略:**
```
增加冗余字段
预计算聚合值
合并表
```

**适用:**
- OLAP 系统
- 读密集场景
- 查询性能要求高

### 3. 分区设计

**策略:**
```
范围分区: 按时间分区
列表分区: 按地区分区
哈希分区: 均匀分布
```

## 索引设计

### 1. 索引类型

```
B-Tree 索引: 等值和范围查询
Hash 索引: 等值查询
全文索引: 文本搜索
空间索引: 地理数据
```

### 2. 索引策略

**原则:**
- 选择性高的列
- 查询频率高的列
- 避免过多索引
- 复合索引顺序

### 3. 索引优化

```sql
-- 分析查询计划
EXPLAIN ANALYZE SELECT * FROM orders WHERE user_id = 1;

-- 添加索引
CREATE INDEX idx_orders_user_id ON orders(user_id);
```

## AI 辅助工具

### 1. 模型生成

```python
# AI 生成 SQLAlchemy 模型
from sqlalchemy import Column, Integer, String, Float, DateTime
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String(100))
    email = Column(String(200), unique=True)
```

### 2. 查询优化

```markdown
请优化这个查询:
```sql
SELECT * FROM orders
WHERE user_id = 1 AND status = 'pending'
ORDER BY created_at DESC;
```

建议索引和查询重写。
```

### 3. 迁移脚本

```markdown
请生成数据库迁移:
- 新增字段: phone (VARCHAR)
- 修改字段: email (增加长度)
- 添加索引: idx_users_phone
```

## 常见问题

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| 查询慢 | 缺少索引 | 添加适当索引 |
| 数据冗余 | 范式不合理 | 重新设计 |
| 锁竞争 | 并发高 | 分区或缓存 |

## 效率提升

### 1. 模板化设计

建立常见业务的数据库模板。

### 2. 自动化迁移

集成 ORM 迁移工具。

### 3. 监控优化

持续监控慢查询并优化。

---

*最后更新: 2026-07-21*

---

## 导航

**分类**: 效率层

**相关文档**:

- [[docs/efficiency/full-cycle-workflow|全周期工作流]]
- [[docs/efficiency/automated-bug-fixing|自动化修复]]
- [[docs/efficiency/anti-patterns|反模式]]
- [[docs/efficiency/context-engineering|上下文工程]]
- [[docs/efficiency/token-optimization|Token 优化]]
