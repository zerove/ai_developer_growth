# API 设计指南 (API Design Guide)

> RESTful API 设计规范与最佳实践。

---

## 1. API 设计原则

**核心理念**: API 是系统的**契约**，设计时要考虑**易用性**和**一致性**。

RESTful 原则:
- 资源导向: URL 代表资源
- HTTP 语义: 正确使用 HTTP 方法
- 无状态: 服务器不保存客户端状态
- 统一接口: 一致的错误处理和响应格式

---

## 2. URL 设计规范

### 2.1 资源命名

```
# 好: 复数名词，小写，连字符
GET    /api/users
GET    /api/users/:id
POST   /api/users
PUT    /api/users/:id
DELETE /api/users/:id

# 差: 动词，大写，下划线
GET    /api/getUsers
GET    /api/user/:id
POST   /api/createUser
```

### 2.2 嵌套资源

```
# 一级嵌套
GET /api/users/:userId/posts
GET /api/users/:userId/posts/:postId

# 避免多级嵌套 (最多 2 级)
GET /api/users/:userId/posts/:postId/comments  # 可以
GET /api/users/:userId/posts/:postId/comments/:commentId/replies  # 避免
```

### 2.3 查询参数

```
# 过滤
GET /api/users?status=active&role=admin

# 分页
GET /api/users?page=1&limit=20

# 排序
GET /api/users?sort=-createdAt,name

# 字段选择
GET /api/users?fields=id,name,email
```

---

## 3. HTTP 方法语义

| 方法 | 语义 | 幂等性 | 安全性 | 示例 |
|------|------|--------|--------|------|
| **GET** | 获取资源 | ✅ | ✅ | 获取用户列表 |
| **POST** | 创建资源 | ❌ | ❌ | 创建新用户 |
| **PUT** | 全量更新 | ✅ | ❌ | 更新用户所有信息 |
| **PATCH** | 部分更新 | ✅ | ❌ | 更新用户邮箱 |
| **DELETE** | 删除资源 | ✅ | ❌ | 删除用户 |

---

## 4. 响应格式规范

### 4.1 成功响应

```json
// 单个资源
{
  "success": true,
  "data": {
    "id": "123",
    "name": "John",
    "email": "john@example.com"
  }
}

// 资源列表
{
  "success": true,
  "data": [
    { "id": "123", "name": "John" },
    { "id": "456", "name": "Jane" }
  ],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total": 100,
    "totalPages": 5
  }
}
```

### 4.2 错误响应

```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid email format",
    "field": "email",
    "details": {
      "expected": "user@example.com",
      "received": "invalid-email"
    }
  }
}
```

### 4.3 HTTP 状态码

| 状态码 | 含义 | 使用场景 |
|--------|------|----------|
| **200** | 成功 | GET、PUT、PATCH 成功 |
| **201** | 已创建 | POST 成功 |
| **204** | 无内容 | DELETE 成功 |
| **400** | 请求错误 | 参数验证失败 |
| **401** | 未认证 | 未登录 |
| **403** | 无权限 | 权限不足 |
| **404** | 未找到 | 资源不存在 |
| **409** | 冲突 | 资源已存在 |
| **422** | 无法处理 | 业务逻辑错误 |
| **500** | 服务器错误 | 系统错误 |

---

## 5. AI 辅助 API 设计

### 5.1 设计 Prompt

```
设计一个用户管理 API，需要:
- 用户注册/登录
- 用户信息 CRUD
- 用户角色管理

请提供:
1. URL 设计
2. 请求/响应格式
3. 错误处理方案
```

### 5.2 代码生成 Prompt

```
根据以下 API 设计生成实现代码:

API: POST /api/users
请求: { name: string, email: string, password: string }
响应: { success: boolean, data: User }

要求:
1. 使用 TypeScript
2. 参数验证 (zod)
3. 错误处理
4. 单元测试
```

---

**📂 导航**
- [[MOC|⬅️ 返回知识地图]]
- **相关**: [[efficiency/error-handling-patterns|错误处理]] | [[efficiency/full-cycle-workflow|全周期工作流]]