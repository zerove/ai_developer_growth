---
title: Express/Fastify Governance Rules
description: > 适用于 Express/Fastify 项目的 AI Agent 开发规范。
category: 工具层
tags: ['测试', 'AI', 'JavaScript', 'API']
difficulty: 初级
reading_time: 10 分钟
updated: 2026-07-21
---

# Express/Fastify Governance Rules

> 适用于 Express/Fastify 项目的 AI Agent 开发规范。

---

## 1. 项目结构

### 分层架构

```
project/
├── src/
│   ├── app.js
│   ├── server.js
│   ├── routes/
│   │   ├── users.js
│   │   └── index.js
│   ├── controllers/
│   │   └── userController.js
│   ├── services/
│   │   └── userService.js
│   ├── repositories/
│   │   └── userRepository.js
│   ├── models/
│   │   └── User.js
│   ├── middleware/
│   │   ├── auth.js
│   │   └── errorHandler.js
│   └── utils/
├── tests/
├── package.json
└── README.md
```

---

## 2. 路由规范

### 路由组织

```javascript
// ✅ 正确: 使用 Router
import { Router } from 'express';
const router = Router();

router.get('/', listUsers);
router.get('/:id', getUser);
router.post('/', createUser);
router.put('/:id', updateUser);
router.delete('/:id', deleteUser);

export default router;

// app.js
import userRoutes from './routes/users.js';
app.use('/api/users', userRoutes);
```

### Fastify 路由

```javascript
// ✅ 正确: Fastify 路由
export default async function userRoutes(fastify, options) {
  fastify.get('/', { schema: listUsersSchema }, listUsers);
  fastify.get('/:id', { schema: getUserSchema }, getUser);
  fastify.post('/', { schema: createUserSchema }, createUser);
}
```

---

## 3. 中间件规范

### 错误处理中间件

```javascript
// ✅ 正确: 全局错误处理
export function errorHandler(err, req, res, next) {
  console.error(err.stack);
  
  const status = err.status || 500;
  const message = err.message || 'Internal Server Error';
  
  res.status(status).json({ error: message });
}

// app.js
app.use(errorHandler);
```

### 认证中间件

```javascript
// ✅ 正确: JWT 认证
export function authenticate(req, res, next) {
  const token = req.headers.authorization?.split(' ')[1];
  
  if (!token) {
    return res.status(401).json({ error: 'No token provided' });
  }
  
  try {
    const decoded = jwt.verify(token, process.env.JWT_SECRET);
    req.user = decoded;
    next();
  } catch (error) {
    return res.status(401).json({ error: 'Invalid token' });
  }
}

// 路由中使用
router.get('/', authenticate, listUsers);
```

---

## 4. 控制器规范

### 控制器设计

```javascript
// ✅ 正确: 控制器只处理请求/响应
export async function listUsers(req, res, next) {
  try {
    const users = await userService.getAll();
    res.json(users);
  } catch (error) {
    next(error);
  }
}

export async function getUser(req, res, next) {
  try {
    const user = await userService.getById(req.params.id);
    if (!user) {
      return res.status(404).json({ error: 'User not found' });
    }
    res.json(user);
  } catch (error) {
    next(error);
  }
}

// ❌ 禁止: 在控制器中包含业务逻辑
export async function listUsers(req, res) {
  const users = await db.query('SELECT * FROM users');  // 应在 service 中
  res.json(users);
}
```

---

## 5. 服务规范

### 服务设计

```javascript
// ✅ 正确: 服务包含业务逻辑
export class UserService {
  constructor(userRepository) {
    this.userRepository = userRepository;
  }
  
  async getAll() {
    return this.userRepository.findAll();
  }
  
  async getById(id) {
    return this.userRepository.findById(id);
  }
  
  async create(data) {
    const existing = await this.userRepository.findByEmail(data.email);
    if (existing) {
      throw new AppError('Email already exists', 400);
    }
    
    return this.userRepository.create(data);
  }
}
```

---

## 6. 测试规范

### 单元测试

```javascript
import { describe, it, expect, vi } from 'vitest';
import { UserService } from '../services/userService.js';

describe('UserService', () => {
  it('should return all users', async () => {
    const mockRepo = {
      findAll: vi.fn().mockResolvedValue([{ id: '1', name: 'John' }])
    };
    
    const service = new UserService(mockRepo);
    const users = await service.getAll();
    
    expect(users).toHaveLength(1);
    expect(mockRepo.findAll).toHaveBeenCalled();
  });
});
```

### 集成测试

```javascript
import request from 'supertest';
import app from '../app.js';

describe('Users API', () => {
  it('GET /api/users should return users', async () => {
    const response = await request(app)
      .get('/api/users')
      .expect(200);
    
    expect(Array.isArray(response.body)).toBe(true);
  });
});
```

---

## 7. 安全规范

### 密钥管理

```javascript
// ❌ 禁止
const API_KEY = 'YOUR_API_KEY_HERE';

// ✅ 正确
const API_KEY = process.env.API_KEY;
if (!API_KEY) {
  throw new Error('API_KEY not set');
}
```

### 安全中间件

```javascript
import helmet from 'helmet';
import cors from 'cors';
import rateLimit from 'express-rate-limit';

// ✅ 正确: 使用安全中间件
app.use(helmet());
app.use(cors({ origin: 'https://example.com' }));
app.use(rateLimit({ windowMs: 15 * 60 * 1000, max: 100 }));
```

---

## 8. 质量检查清单

### 代码质量

- [ ] ESLint 通过
- [ ] 无空 catch 块
- [ ] 控制器只处理请求/响应
- [ ] 业务逻辑在服务层
- [ ] 无硬编码密钥

### 测试质量

- [ ] 核心逻辑测试覆盖 > 80%
- [ ] 所有测试通过
- [ ] 使用 supertest 进行 API 测试
- [ ] Mock 使用正确

### 安全

- [ ] 使用 helmet
- [ ] CORS 配置正确
- [ ] 速率限制配置
- [ ] 输入验证完整

---

*本规范随 Express/Fastify 生态演进持续更新。最后更新: 2026-07-17*
