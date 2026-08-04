---
title: GraphQL Governance Rules
description: > 适用于 GraphQL 项目的 AI Agent 开发规范。
category: 工具层
tags: ['AI', 'GraphQL', '测试', 'Python', 'JavaScript']
difficulty: 高级
reading_time: 10 分钟
updated: 2026-07-21
---

# GraphQL Governance Rules

> 适用于 GraphQL 项目的 AI Agent 开发规范。

---

## 1. Schema 设计

### 类型定义

```graphql
# ✅ 正确: 清晰的类型定义
type User {
  id: ID!
  email: String!
  name: String!
  posts: [Post!]!
  createdAt: DateTime!
}

type Post {
  id: ID!
  title: String!
  content: String!
  author: User!
  createdAt: DateTime!
}

# ❌ 禁止: 模糊的类型
type User {
  id: ID
  data: JSON  # 应明确字段
}
```

### 输入类型

```graphql
# ✅ 正确: 使用 Input 类型
input CreateUserInput {
  email: String!
  name: String!
  password: String!
}

input UpdateUserInput {
  email: String
  name: String
}

# ❌ 禁止: 直接使用对象类型
mutation createUser($user: User!) {  # 应使用 Input 类型
  createUser(user: $user) { id }
}
```

---

## 2. 查询设计

### 查询深度限制

```python
# ✅ 正确: 限制查询深度
from graphql import ValidationRule

class DepthLimitRule(ValidationRule):
    def __init__(self, max_depth=5):
        self.max_depth = max_depth
    
    # 实现深度检查
```

### 字段级授权

```graphql
# ✅ 正确: 使用 @auth 指令
type User {
  id: ID!
  email: String! @auth(requires: ADMIN)
  name: String!
  ssn: String @auth(requires: OWNER)
}
```

---

## 3. 解析器规范

### N+1 问题解决

```python
# ✅ 正确: 使用 DataLoader
from aiodataloader import DataLoader

async def load_user(user_ids):
    users = await db.users.find({"_id": {"$in": user_ids}})
    return [users.get(id) for id in user_ids]

user_loader = DataLoader(load_fn=load_user)

# 解析器中使用
async def resolve_posts(user, info):
    return await post_loader.load(user.id)
```

### 错误处理

```python
# ✅ 正确: 使用 GraphQL 错误
from graphql import GraphQLError

async def resolve_user(obj, info, id):
    user = await db.users.find_one({"_id": id})
    if not user:
        raise GraphQLError('User not found', extensions={'code': 'NOT_FOUND'})
    return user
```

---

## 4. 变更设计

### 变更返回

```graphql
# ✅ 正确: 变更返回完整对象
type Mutation {
  createUser(input: CreateUserInput!): CreateUserPayload!
  updateUser(id: ID!, input: UpdateUserInput!): UpdateUserPayload!
}

type CreateUserPayload {
  user: User
  errors: [UserError!]
}

type UserError {
  field: String
  message: String!
  code: ErrorCode!
}
```

### 乐观更新

```javascript
// ✅ 正确: 客户端乐观更新
const updateUser = useMutation(UPDATE_USER, {
  optimisticResponse: {
    updateUser: {
      user: { ...currentUser, ...newData },
      errors: []
    }
  }
});
```

---

## 5. 订阅规范

### WebSocket 订阅

```graphql
# ✅ 正确: 使用订阅
type Subscription {
  userCreated: User!
  postUpdated(id: ID!): Post!
}

# 服务端实现
async def subscribe_user_created(root, info):
    async with pubsub.async_iter('user_created') as iterator:
        async for user in iterator:
            yield {'userCreated': user}
```

---

## 6. 测试规范

### 查询测试

```python
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_get_user():
    query = '''
    query GetUser($id: ID!) {
        user(id: $id) {
            id
            name
            email
        }
    }
    '''
    
    async with AsyncClient(app=app, base_url='http://test') as client:
        response = await client.post(
            '/graphql',
            json={'query': query, 'variables': {'id': '123'}}
        )
        assert response.status_code == 200
        assert 'data' in response.json()
```

### 变更测试

```python
@pytest.mark.asyncio
async def test_create_user():
    mutation = '''
    mutation CreateUser($input: CreateUserInput!) {
        createUser(input: $input) {
            user { id name }
            errors { message }
        }
    }
    '''
    
    variables = {
        'input': {
            'email': 'test@example.com',
            'name': 'John',
            'password': 'secret123'
        }
    }
    
    async with AsyncClient(app=app, base_url='http://test') as client:
        response = await client.post(
            '/graphql',
            json={'query': mutation, 'variables': variables}
        )
        assert response.status_code == 200
```

---

## 7. 安全规范

### 查询复杂度分析

```python
# ✅ 正确: 限制查询复杂度
from graphql import parse
from graphql.language import visitor

def calculate_complexity(query, max_complexity=1000):
    # 实现复杂度计算
    pass
```

### 深度过滤

```graphql
# ✅ 正确: 限制嵌套深度
# 查询深度不应超过 5 层
query {
  users {
    posts {
      comments {
        author {
          posts {  # 超过 5 层，应拒绝
            title
          }
        }
      }
    }
  }
}
```

---

## 8. 质量检查清单

### Schema

- [ ] 类型定义清晰
- [ ] Input 类型使用
- [ ] 非空字段标记
- [ ] 枚举类型使用

### 查询

- [ ] 深度限制
- [ ] 复杂度分析
- [ ] N+1 问题解决
- [ ] 错误处理完整

### 安全

- [ ] 认证授权
- [ ] 查询白名单
- [ ] 速率限制
- [ ] 内存限制

---

*本规范随 GraphQL 生态演进持续更新。最后更新: 2026-07-17*
