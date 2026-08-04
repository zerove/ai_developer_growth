# Express.js 开发规则

> 基于 TypeScript 的 Express.js 开发标准

---

## 核心约定

### 文件组织

```
src/
├── controllers/    # 请求处理
├── services/       # 业务逻辑
├── middleware/     # 中间件
├── routes/         # 路由定义
├── models/         # 数据模型
├── types/          # 类型定义
├── utils/          # 工具函数
├── config/         # 配置
├── app.ts          # Express 应用
└── server.ts       # 启动入口
```

### 命名规范

- **文件**: `camelCase.ts`
- **类**: `PascalCase` (UserController)
- **函数**: `camelCase` (getUsers)
- **路由**: `snake_case` (userRoutes)

---

## API 规范

```ts
// ✅ 推荐的控制器结构
import { Request, Response, NextFunction } from 'express';
import { UserService } from './user.service';

export class UserController {
  constructor(private userService: UserService) {}

  async findAll(req: Request, res: Response, next: NextFunction) {
    try {
      const page = parseInt(req.query.page as string) || 1;
      const users = await this.userService.findAll({ page });
      res.json({ data: users, page });
    } catch (error) {
      next(error);  // 交给错误中间件
    }
  }

  async create(req: Request, res: Response, next: NextFunction) {
    try {
      const user = await this.userService.create(req.body);
      res.status(201).json({ data: user });
    } catch (error) {
      next(error);
    }
  }
}
```

---

## 质量门禁

### Lint

```bash
# 检查
npx eslint src/ --ext .ts
npx tsc --noEmit

# 格式化
npx prettier --check src/
```

### 测试

```bash
# 测试
npx vitest run
# 或
npx jest --coverage
```

---

## 错误处理

```ts
// ✅ 全局错误中间件
export class AppError extends Error {
  constructor(
    public statusCode: number,
    public message: string,
    public code?: string,
  ) {
    super(message);
  }
}

export function errorHandler(
  err: Error,
  _req: Request,
  res: Response,
  _next: NextFunction,
) {
  if (err instanceof AppError) {
    return res.status(err.statusCode).json({
      error: { code: err.code, message: err.message },
    });
  }

  // 未预期的错误
  console.error('Unexpected error:', err);
  res.status(500).json({
    error: { message: 'Internal server error' },
  });
}
```

---

## 路由结构

```ts
// ✅ 清晰的路由分离
import { Router } from 'express';
import { UserController } from '../controllers/user.controller';
import { auth } from '../middleware/auth';
import { validate } from '../middleware/validate';

const router = Router();
const controller = new UserController(userService);

router.get('/', auth, controller.findAll.bind(controller));
router.get('/:id', auth, controller.findById.bind(controller));
router.post('/', auth, validate(createUserSchema), controller.create.bind(controller));
router.put('/:id', auth, validate(updateUserSchema), controller.update.bind(controller));
router.delete('/:id', auth, controller.delete.bind(controller));

export { router as userRoutes };
```

---

## 常用依赖

| 用途 | 推荐包 |
|------|--------|
| 类型安全 | zod / typebox |
| 认证 | passport / jsonwebtoken |
| ORM | prisma / drizzle |
| 日志 | pino / winston |
| 验证 | zod-express-middleware |
| 测试 | vitest + supertest |
