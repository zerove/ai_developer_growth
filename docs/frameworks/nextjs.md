# Next.js Governance Rules

> 适用于 Next.js 项目的 AI Agent 开发规范。

---

## 1. 渲染策略

### Server Components 优先

```tsx
// ✅ 正确: Server Component (默认)
export default async function UserPage({ params }: { params: { id: string } }) {
  const user = await getUser(params.id);
  return <UserProfile user={user} />;
}

// ❌ 禁止: 不必要的 Client Component
'use client';
export default function UserPage({ params }: { params: { id: string } }) {
  const [user, setUser] = useState(null);
  
  useEffect(() => {
    getUser(params.id).then(setUser);
  }, [params.id]);
  
  return <UserProfile user={user} />;
}
```

### Client Components

```tsx
// ✅ 正确: 仅在需要交互时使用 'use client'
'use client';

import { useState } from 'react';

export function UserCard({ user }: { user: User }) {
  const [expanded, setExpanded] = useState(false);
  
  return (
    <div onClick={() => setExpanded(!expanded)}>
      {user.name}
      {expanded && <p>{user.bio}</p>}
    </div>
  );
}
```

---

## 2. 数据获取

### Server Actions

```tsx
// ✅ 正确: 使用 Server Actions
'use server';

export async function createUser(formData: FormData) {
  const name = formData.get('name') as string;
  const email = formData.get('email') as string;
  
  const user = await db.user.create({ data: { name, email } });
  revalidatePath('/users');
  return user;
}

// ❌ 禁止: 不必要的 API Route
// app/api/users/route.ts
export async function POST(request: Request) {
  const data = await request.json();
  const user = await db.user.create({ data });
  return Response.json(user);
}
```

### 数据获取模式

```tsx
// ✅ 正确: Server Component 中直接获取
export default async function UsersPage() {
  const users = await getUsers();
  return <UserList users={users} />;
}

// ✅ 正确: 并发获取
export default async function DashboardPage() {
  const [users, posts, stats] = await Promise.all([
    getUsers(),
    getPosts(),
    getStats(),
  ]);
  
  return (
    <div>
      <UserList users={users} />
      <PostList posts={posts} />
      <Stats stats={stats} />
    </div>
  );
}
```

---

## 3. 路由规范

### 文件路由

```
app/
├── page.tsx              # /
├── layout.tsx            # 根布局
├── about/
│   └── page.tsx          # /about
├── users/
│   ├── page.tsx          # /users
│   └── [id]/
│       ├── page.tsx      # /users/:id
│       └── layout.tsx    # /users/:id 布局
└── api/
    └── users/
        └── route.ts      # /api/users
```

### 动态路由

```tsx
// ✅ 正确: 使用 params
export default async function UserPage({ 
  params 
}: { 
  params: { id: string } 
}) {
  const user = await getUser(params.id);
  return <UserProfile user={user} />;
}

// ❌ 禁止: 使用 searchParams 获取路由参数
export default async function UserPage({ 
  searchParams 
}: { 
  searchParams: { id: string } 
}) {
  const user = await getUser(searchParams.id);  // 错误!
}
```

---

## 4. 性能优化

### Image 组件

```tsx
// ✅ 正确
import Image from 'next/image';

<Image
  src="/avatar.png"
  alt="User avatar"
  width={100}
  height={100}
  placeholder="blur"
/>

// ❌ 禁止: 使用 img 标签
<img src="/avatar.png" alt="User avatar" />
```

### Link 组件

```tsx
// ✅ 正确
import Link from 'next/link';

<Link href="/about">About</Link>

// ❌ 禁止: 使用 a 标签
<a href="/about">About</a>
```

### 字体优化

```tsx
// ✅ 正确
import { Inter } from 'next/font/google';

const inter = Inter({ subsets: ['latin'] });

export default function Layout({ children }) {
  return <body className={inter.className}>{children}</body>;
}
```

---

## 5. 测试规范

### Playwright (E2E)

```typescript
import { test, expect } from '@playwright/test';

test('displays user profile', async ({ page }) => {
  await page.goto('/users/1');
  await expect(page.locator('h1')).toContainText('John');
});

test('creates user', async ({ page }) => {
  await page.goto('/users/new');
  await page.fill('input[name="name"]', 'John');
  await page.fill('input[name="email"]", 'john@example.com');
  await page.click('button[type="submit"]');
  await expect(page).toHaveURL('/users');
});
```

### Jest (Unit)

```typescript
import { render, screen } from '@testing-library/react';
import UserCard from './UserCard';

test('renders user name', () => {
  render(<UserCard user={{ id: '1', name: 'John' }} />);
  expect(screen.getByText('John')).toBeInTheDocument();
});
```

---

## 6. 项目结构

```
project/
├── app/
│   ├── layout.tsx
│   ├── page.tsx
│   ├── users/
│   │   ├── page.tsx
│   │   └── [id]/
│   │       └── page.tsx
│   └── api/
├── components/
├── lib/
├── types/
├── next.config.js
├── package.json
└── README.md
```

---

## 7. 安全规范

### 环境变量

```typescript
// ❌ 禁止
const API_KEY = 'sk-1234567890';

// ✅ 正确: 服务端
const API_KEY = process.env.API_KEY;

// ✅ 正确: 客户端 (NEXT_PUBLIC_ 前缀)
const PUBLIC_KEY = process.env.NEXT_PUBLIC_PUBLIC_KEY;
```

### Server Actions 安全

```tsx
'use server';

// ✅ 正确: 验证输入
export async function updateUser(formData: FormData) {
  const id = formData.get('id') as string;
  const name = formData.get('name') as string;
  
  // 验证
  if (!id || !name) {
    throw new Error('Missing required fields');
  }
  
  // 验证权限
  const session = await getServerSession();
  if (!session) {
    throw new Error('Unauthorized');
  }
  
  await db.user.update({ where: { id }, data: { name } });
}
```

---

## 8. 质量检查清单

### 代码质量

- [ ] ESLint 通过
- [ ] TypeScript 无错误
- [ ] Server Components 优先
- [ ] 无不必要的 'use client'
- [ ] 无硬编码密钥

### 性能

- [ ] 使用 next/image 优化图片
- [ ] 使用 next/link 优化链接
- [ ] 使用 Server Components 获取数据
- [ ] 无客户端数据获取 (除非必要)

### 测试

- [ ] E2E 测试覆盖核心流程
- [ ] 单元测试覆盖工具函数
- [ ] 所有测试通过

---

*本规范随 Next.js 生态演进持续更新。最后更新: 2026-07-17*
