# Next.js (App Router) 开发规则

> 基于 React + TypeScript 的 Next.js App Router 开发标准

---

## 核心约定

### 文件组织

```
app/
├── (auth)/                # 路由组
│   ├── login/
│   │   └── page.tsx
│   └── register/
│       └── page.tsx
├── api/                    # API 路由
│   └── users/
│       └── route.ts
├── layout.tsx              # 根布局
└── page.tsx                # 首页
lib/                        # 共享逻辑
├── actions/                # Server Actions
├── db/                     # 数据库
└── utils/
components/
├── ui/                     # UI 组件
└── features/               # 功能组件
```

### 命名规范

- **页面**: `page.tsx`
- **布局**: `layout.tsx`
- **加载**: `loading.tsx`
- **错误**: `error.tsx`
- **API 路由**: `route.ts`
- **Server Action**: `actions.ts`

---

## 组件模式

### 服务器组件 (默认)

```tsx
// app/users/page.tsx — 服务器组件 (默认)
export default async function UsersPage() {
  const users = await db.user.findMany();
  return <UserList users={users} />;
}
```

### 客户端组件

```tsx
'use client';

// app/users/_components/user-list.tsx — 客户端组件
export function UserList({ users }: { users: User[] }) {
  const [selected, setSelected] = useState<string | null>(null);
  return <div>{/* 交互逻辑 */}</div>;
}
```

---

## 质量门禁

### Lint

```bash
# 检查
npx next lint

# 类型检查
npx tsc --noEmit
```

### 测试

```bash
# 单元测试
npx vitest run

# E2E
npx playwright test
```

---

## Server Actions

```ts
// lib/actions/users.ts
'use server';

import { revalidatePath } from 'next/cache';
import { z } from 'zod';

const createUserSchema = z.object({
  name: z.string().min(1),
  email: z.string().email(),
});

export async function createUser(formData: FormData) {
  'use server';

  const data = createUserSchema.parse({
    name: formData.get('name'),
    email: formData.get('email'),
  });

  await db.user.create({ data });
  revalidatePath('/users');
}
```

---

## 常用依赖

| 用途 | 推荐包 |
|------|--------|
| 数据库 | prisma / drizzle |
| 认证 | next-auth / clerk |
| 表单 | react-hook-form |
| UI | shadcn/ui |
| 数据校验 | zod |
| 测试 | vitest + playwright |
