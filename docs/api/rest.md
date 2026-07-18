# RESTful API Governance Rules

> 适用于 RESTful API 设计的 AI Agent 开发规范。

---

## 1. URL 设计

### 资源命名

```
# ✅ 正确: 使用复数名词
GET    /users           # 获取用户列表
GET    /users/:id       # 获取单个用户
POST   /users           # 创建用户
PUT    /users/:id       # 更新用户
DELETE /users/:id       # 删除用户

# ❌ 禁止: 使用动词
GET    /getUsers
POST   /createUser
PUT    /updateUser
DELETE /deleteUser
```

### 嵌套资源

```
# ✅ 正确: 合理嵌套
GET    /users/:id/posts           # 用户的文章
GET    /users/:id/posts/:postId   # 用户的某篇文章

# ❌ 禁止: 过深嵌套
GET    /users/:id/posts/:postId/comments/:commentId/replies
```

### 过滤和分页

```
# ✅ 正确: 使用查询参数
GET /users?role=admin&status=active
GET /posts?page=2&limit=20
GET /posts?sort=-createdAt,title
```

---

## 2. HTTP 状态码

### 正确使用

```python
# ✅ 正确
@router.get('/users/{id}')
async def get_user(id: str):
    user = await get_user_by_id(id)
    if not user:
        raise HTTPException(status_code=404, detail='User not found')
    return user

@router.post('/users')
async def create_user(user: UserCreate):
    # 201 Created
    return await create_user(user), 201

@router.put('/users/{id}')
async def update_user(id: str, user: UserUpdate):
    # 200 OK 或 204 No Content
    await update_user(id, user)
    return Response(status_code=204)
```

### 状态码列表

| 状态码 | 含义 | 使用场景 |
|--------|------|----------|
| 200 | OK | 成功 GET/PUT |
| 201 | Created | 成功 POST |
| 204 | No Content | 成功 DELETE |
| 400 | Bad Request | 参数错误 |
| 401 | Unauthorized | 未认证 |
| 403 | Forbidden | 无权限 |
| 404 | Not Found | 资源不存在 |
| 409 | Conflict | 资源冲突 |
| 422 | Unprocessable Entity | 验证错误 |
| 429 | Too Many Requests | 速率限制 |
| 500 | Internal Server Error | 服务器错误 |

---

## 3. 请求/响应格式

### JSON 格式

```json
// ✅ 正确: 统一格式
{
  "data": {
    "id": "123",
    "name": "John",
    "email": "john@example.com"
  },
  "meta": {
    "page": 1,
    "limit": 20,
    "total": 100
  }
}

// ❌ 禁止: 不一致的格式
{
  "user": {
    "id": "123",
    "name": "John"
  }
}
```

### 错误格式

```json
// ✅ 正确: 统一错误格式
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid input",
    "details": [
      {
        "field": "email",
        "message": "Invalid email format"
      }
    ]
  }
}
```

---

## 4. 版本控制

### URL 版本

```
# ✅ 正确
GET /api/v1/users
GET /api/v2/users

# ❌ 禁止: 无版本
GET /api/users
```

### Header 版本

```
# ✅ 正确: 使用 Accept header
Accept: application/vnd.myapp.v1+json

# 或使用自定义 header
X-API-Version: 1
```

---

## 5. 认证与授权

### JWT Token

```
# ✅ 正确: 使用 Bearer Token
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...

# 响应头
X-Access-Token: eyJhbGciOiJIUzI1NiIs...
X-Refresh-Token: eyJhbGciOiJIUzI1NiIs...
```

### OAuth 2.0

```
# ✅ 正确: OAuth 2.0 流程
POST /oauth/token
Content-Type: application/x-www-form-urlencoded

grant_type=authorization_code
&code=xxx
&redirect_uri=xxx
&client_id=xxx
```

---

## 6. 测试规范

### API 测试

```python
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_get_users():
    async with AsyncClient(app=app, base_url='http://test') as client:
        response = await client.get('/api/v1/users')
        assert response.status_code == 200
        assert 'data' in response.json()

@pytest.mark.asyncio
async def test_create_user():
    async with AsyncClient(app=app, base_url='http://test') as client:
        response = await client.post(
            '/api/v1/users',
            json={'email': 'test@example.com', 'name': 'John'}
        )
        assert response.status_code == 201
```

### 负载测试

```bash
# ✅ 正确: 使用 k6 进行负载测试
k6 run --vus 10 --duration 30s script.js
```

---

## 7. 文档规范

### OpenAPI/Swagger

```yaml
# ✅ 正确: 完整的 API 文档
openapi: 3.0.0
info:
  title: User API
  version: 1.0.0
paths:
  /users:
    get:
      summary: List users
      parameters:
        - name: page
          in: query
          schema:
            type: integer
      responses:
        '200':
          description: Success
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/UserList'
```

---

## 8. 质量检查清单

### URL 设计

- [ ] 使用复数名词
- [ ] 合理的嵌套层级
- [ ] 版本控制
- [ ] 查询参数过滤

### 响应格式

- [ ] 统一 JSON 格式
- [ ] 统一错误格式
- [ ] 正确的 HTTP 状态码
- [ ] 分页信息完整

### 安全

- [ ] 认证机制
- [ ] 速率限制
- [ ] 输入验证
- [ ] CORS 配置

---

*本规范随 REST API 最佳实践演进持续更新。最后更新: 2026-07-17*
