# NoSQL Governance Rules

> 适用于 NoSQL 数据库的 AI Agent 开发规范。

---

## 1. 数据模型设计

### MongoDB 文档设计

```javascript
// ✅ 正确: 嵌入相关数据
{
  _id: ObjectId("..."),
  name: "John",
  email: "john@example.com",
  posts: [
    {
      title: "First Post",
      content: "...",
      createdAt: ISODate("2024-01-01")
    }
  ],
  createdAt: ISODate("2024-01-01")
}

// ❌ 禁止: 过度引用
{
  _id: ObjectId("..."),
  name: "John",
  email: "john@example.com",
  postIds: [ObjectId("..."), ObjectId("...")]  // 需要额外查询
}
```

### Redis 数据结构

```python
# ✅ 正确: 选择合适的数据结构
# 用户会话
redis.hset("session:123", mapping={
    "user_id": "user1",
    "expires": "1704067200"
})

# 排行榜
redis.zadd("leaderboard", {"user1": 100, "user2": 200})

# 缓存
redis.setex("user:123", 3600, json.dumps(user_data))

# ❌ 禁止: 使用字符串存储复杂对象
redis.set("user:123", json.dumps(user_data))  # 应使用 Hash
```

---

## 2. 查询优化

### MongoDB 索引

```javascript
// ✅ 正确: 创建合适的索引
db.users.createIndex({ email: 1 }, { unique: true });
db.posts.createIndex({ authorId: 1, createdAt: -1 });

// ✅ 正确: 复合索引
db.orders.createIndex({ 
    userId: 1, 
    status: 1, 
    createdAt: -1 
});

// ❌ 禁止: 过度索引
db.users.createIndex({ name: 1 });  // 很少查询
db.users.createIndex({ createdAt: 1 });  // 很少查询
```

### 查询优化

```javascript
// ✅ 正确: 使用投影限制返回字段
db.users.find({ email: "john@example.com" }, { 
    name: 1, 
    email: 1 
});

// ❌ 禁止: 返回所有字段
db.users.find({ email: "john@example.com" });
```

---

## 3. 一致性策略

### 最终一致性

```python
# ✅ 正确: 接受最终一致性
async def get_user(user_id: str):
    # 先查缓存
    cached = await redis.get(f"user:{user_id}")
    if cached:
        return json.loads(cached)
    
    # 缓存未命中，查数据库
    user = await db.users.find_one({"_id": user_id})
    if user:
        # 写入缓存
        await redis.setex(
            f"user:{user_id}", 
            3600, 
            json.dumps(user)
        )
    
    return user
```

### 事务 (MongoDB 4.0+)

```python
# ✅ 正确: 需要强一致性时使用事务
async def transfer_money(from_id: str, to_id: str, amount: int):
    async with await client.start_session() as session:
        async with session.start_transaction():
            await db.accounts.update_one(
                {"_id": from_id},
                {"$inc": {"balance": -amount}},
                session=session
            )
            await db.accounts.update_one(
                {"_id": to_id},
                {"$inc": {"balance": amount}},
                session=session
            )
```

---

## 4. Redis 使用规范

### 缓存策略

```python
# ✅ 正确: Cache-Aside 模式
async def get_user(user_id: str):
    # 1. 查缓存
    cache_key = f"user:{user_id}"
    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)
    
    # 2. 查数据库
    user = await db.users.find_one({"_id": user_id})
    if user:
        # 3. 写入缓存
        await redis.setex(cache_key, 3600, json.dumps(user))
    
    return user

# ✅ 正确: 缓存失效
async def update_user(user_id: str, data: dict):
    await db.users.update_one({"_id": user_id}, {"$set": data})
    # 失效缓存
    await redis.delete(f"user:{user_id}")
```

### Key 设计

```python
# ✅ 正确: 命名规范
"user:{id}"           # 用户对象
"user:{id}:posts"     # 用户的文章列表
"post:{id}"           # 文章对象
"session:{id}"        # 会话
"rate_limit:{ip}"     # 速率限制

# ❌ 禁止: 混乱的命名
"u123"                # 不清晰
"cache_user_data"     # 不规范
```

---

## 5. 测试规范

### MongoDB 测试

```python
import pytest
from motor.motor_asyncio import AsyncIOMotorClient

@pytest.fixture
async def db():
    client = AsyncIOMotorClient('mongodb://localhost:27017')
    db = client.test_db
    yield db
    # 清理测试数据
    await db.users.drop()
    await db.posts.drop()

async def test_create_user(db):
    result = await db.users.insert_one({
        "name": "John",
        "email": "john@example.com"
    })
    assert result.inserted_id is not None
```

### Redis 测试

```python
import pytest
import fakeredis.aioredis

@pytest.fixture
async def redis():
    server = fakeredis.aioredis.FakeServer()
    client = await fakeredis.aioredis.create_redis(server=server)
    yield client
    client.close()

async def test_cache_user(redis):
    await redis.setex("user:123", 3600, '{"name": "John"}')
    cached = await redis.get("user:123")
    assert cached is not None
```

---

## 6. 质量检查清单

### 数据模型

- [ ] 合理的嵌入/引用
- [ ] 文档大小限制
- [ ] 索引设计
- [ ] 数据类型选择

### 查询

- [ ] 使用投影
- [ ] 避免全表扫描
- [ ] 合理的分页
- [ ] 批量操作

### 缓存

- [ ] 缓存策略选择
- [ ] 缓存失效机制
- [ ] 过期时间设置
- [ ] 缓存击穿防护

---

*本规范随 NoSQL 生态演进持续更新。最后更新: 2026-07-17*
