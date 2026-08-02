---
title: Redis
description: > 内存数据库，缓存、会话、排行榜、分布式锁的首选。
category: 工具层
tags: ['AI', 'Python', 'SQL', '数据库', 'Docker']
difficulty: 基础
reading_time: 10 分钟
updated: 2026-07-21
---

# Redis

> 内存数据库，缓存、会话、排行榜、分布式锁的首选。

---

## 1. 核心问题

数据库查询耗时 50ms+，每次请求都打到数据库。热点数据被频繁读取，数据库不堪重负。

Redis 把数据放内存，读取延迟降到 < 1ms。但用错模式会导致缓存穿透、雪崩、数据不一致。

---

## 2. 数据结构选型

| 结构 | 命令 | 场景 |
|------|------|------|
| String | `GET` / `SET` / `SETEX` | 简单缓存、计数器 |
| Hash | `HGET` / `HSET` | 对象属性缓存 |
| List | `LPUSH` / `RPOP` | 消息队列、最新列表 |
| Set | `SADD` / `SMEMBERS` | 标签、去重 |
| Sorted Set | `ZADD` / `ZRANGE` | 排行榜、延迟队列 |
| Stream | `XADD` / `XREAD` | 事件流（替代轻量 Kafka） |

```bash
# ✅ Hash 缓存用户对象（比 String 序列化整个 JSON 更灵活）
HSET user:1001 name "张三" email "zhang@example.com" score 95
HGET user:1001 name

# ❌ 不要：把整个对象序列化成一个 String
SET user:1001 '{"name":"张三","email":"zhang@example.com"}'
# 无法更新单个字段，每次都要全量读写
```

---

## 3. 缓存模式

### Cache-Aside（旁路缓存）

```python
def get_user(user_id):
    # 先查缓存
    cached = redis.get(f"user:{user_id}")
    if cached:
        return json.loads(cached)

    # 缓存未命中，查数据库
    user = db.query("SELECT * FROM users WHERE id = %s", user_id)
    if user:
        # 写入缓存，设置 TTL
        redis.setex(f"user:{user_id}", 3600, json.dumps(user))
    return user

def update_user(user_id, data):
    db.execute("UPDATE users SET ... WHERE id = %s", user_id)
    redis.delete(f"user:{user_id}")  # 删除缓存，而非更新
```

Cache-Aside 最简单可靠。更新策略：删除缓存优于更新缓存（避免并发写覆盖）。

### Write-Through（写穿透）

```python
def update_user(user_id, data):
    db.execute("UPDATE users SET ... WHERE id = %s", user_id)
    redis.setex(f"user:{user_id}", 3600, json.dumps(data))  # 写 DB 同时写缓存
```

适合读多写少的场景。写操作略慢但缓存始终一致。

---

## 4. 缓存防护

```python
# 缓存穿透：查询不存在的数据
# 解法：布隆过滤器 或 缓存空值
def get_user(user_id):
    cached = redis.get(f"user:{user_id}")
    if cached == "NULL":  # 空值标记
        return None
    if cached:
        return json.loads(cached)

    user = db.query("SELECT * FROM users WHERE id = %s", user_id)
    if user:
        redis.setex(f"user:{user_id}", 3600, json.dumps(user))
    else:
        redis.setex(f"user:{user_id}", 300, "NULL")  # 空值缓存 5 分钟
    return user

# 缓存雪崩：大量 key 同时过期
# 解法：TTL 加随机偏移
import random
ttl = 3600 + random.randint(0, 600)  # 3600-4200 秒随机过期
redis.setex(f"user:{user_id}", ttl, json.dumps(user))
```

---

## 5. 持久化与高可用

```yaml
# docker-compose: Sentinel 模式
services:
  redis-master:
    image: redis:7-alpine
    command: redis-server --appendonly yes --requirepass ${REDIS_PASSWORD}
    volumes:
      - redis_data:/data

  redis-sentinel:
    image: redis:7-alpine
    volumes:
      - ./sentinel.conf:/etc/sentinel.conf
    command: redis-sentinel /etc/sentinel.conf
```

```conf
# sentinel.conf
sentinel monitor mymaster redis-master 6379 2  # 2 个哨兵同意才故障转移
sentinel down-after-milliseconds mymaster 5000
sentinel failover-timeout mymaster 10000
```

数据量超过单机内存时，用 Redis Cluster 分片（16384 个 slot 分布到多个节点）。

---

## 6. 常见陷阱

| 陷阱 | 原因 | 解法 |
|------|------|------|
| 大 Key | Hash/Set 元素过多 | 拆分、限制大小 |
| 热 Key | 单 key QPS 过万 | 本地缓存 + 多副本 |
| 慢命令 | `KEYS *`、`SORT` | 用 `SCAN` 替代，避免 O(N) |
| 内存暴涨 | 未设 TTL | 所有 key 必须有 TTL |

---

## 相关文档

- [[docs/caching/cdn|CDN 缓存]] — 边缘层缓存
- [[docs/database/sql|SQL]] — 数据库缓存优化
- [[docs/devops/docker|Docker]] — Redis 容器化
- [[docs/monitoring/prometheus-grafana|Prometheus + Grafana]] — Redis Exporter 监控

---

*本规范随 Redis 生态演进持续更新。最后更新: 2026-07-20*
