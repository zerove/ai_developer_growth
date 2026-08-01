---
title: Svelte Governance Rules
description: > 适用于 Svelte/SvelteKit 项目的 AI Agent 开发规范。
category: 工具层
tags: ['测试', 'AI', 'TypeScript', 'API']
difficulty: 初级
reading_time: 10 分钟
updated: 2026-07-21
---

# Svelte Governance Rules

> 适用于 Svelte/SvelteKit 项目的 AI Agent 开发规范。

---

## 1. 组件规范

### 使用 Svelte 5 Runes (推荐)

```svelte
<script lang="ts">
  // ✅ 正确: 使用 runes
  let count = $state(0);
  let doubled = $derived(count * 2);
  
  function increment() {
    count++;
  }
  
  // ✅ 正确: 使用 $effect
  $effect(() => {
    console.log('Count changed:', count);
  });
</script>

<button onclick={increment}>
  Count: {count}, Doubled: {doubled}
</button>
```

### Props

```svelte
<script lang="ts">
  // ✅ 正确: 使用 $props
  let { user, onSelect }: { user: User; onSelect: (user: User) => void } = $props();
</script>

<div onclick={() => onSelect(user)}>
  {user.name}
</div>
```

### 禁止行为

```svelte
<!-- ❌ 禁止: 使用旧语法 -->
<script lang="ts">
  export let user: User;  // 应使用 $props
  export let onSelect: (user: User) => void;
  
  $: doubled = count * 2;  // 应使用 $derived
</script>
```

---

## 2. 状态管理

### SvelteKit Stores

```typescript
// ✅ 正确: 使用 writable store
import { writable } from 'svelte/store';

export const userStore = writable<User | null>(null);

// ✅ 正确: 使用 derived store
export const isLoggedIn = derived(userStore, $user => $user !== null);
```

### 页面状态

```svelte
<!-- ✅ 正确: 使用 page store -->
<script lang="ts">
  import { page } from '$app/stores';
  
  let userId = $derived($page.params.id);
</script>
```

---

## 3. SvelteKit 路由

### 文件路由

```
src/routes/
├── +page.svelte              # /
├── +layout.svelte            # 根布局
├── about/
│   └── +page.svelte          # /about
├── users/
│   ├── +page.svelte          # /users
│   └── [id]/
│       ├── +page.svelte      # /users/:id
│       └── +page.server.ts   # 服务端加载
└── api/
    └── users/
        └── +server.ts        # /api/users
```

### 加载函数

```typescript
// ✅ 正确: 使用 load 函数
// src/routes/users/[id]/+page.server.ts
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ params }) => {
  const user = await getUser(params.id);
  return { user };
};

// src/routes/users/[id]/+page.svelte
<script lang="ts">
  let { data } = $props();
  let { user } = data;
</script>

<h1>{user.name}</h1>
```

---

## 4. 表单处理

### Form Actions

```typescript
// ✅ 正确: 使用 form actions
// src/routes/users/create/+page.server.ts
import type { Actions } from './$types';
import { fail } from '@sveltejs/kit';

export const actions: Actions = {
  default: async ({ request }) => {
    const formData = await request.formData();
    const name = formData.get('name');
    
    if (!name) {
      return fail(400, { name, error: 'Name is required' });
    }
    
    await createUser({ name });
    return { success: true };
  }
};
```

```svelte
<!-- ✅ 正确: 使用 enhance -->
<form method="POST" use:enhance>
  <input name="name" />
  <button type="submit">Create</button>
</form>
```

---

## 5. 测试规范

### Vitest

```typescript
import { render, screen } from '@testing-library/svelte';
import { describe, it, expect } from 'vitest';
import UserCard from './UserCard.svelte';

describe('UserCard', () => {
  it('renders user name', () => {
    render(UserCard, {
      props: {
        user: { id: '1', name: 'John' },
        onSelect: () => {}
      }
    });
    
    expect(screen.getByText('John')).toBeInTheDocument();
  });
});
```

### Playwright (E2E)

```typescript
import { test, expect } from '@playwright/test';

test('displays user profile', async ({ page }) => {
  await page.goto('/users/1');
  await expect(page.locator('h1')).toContainText('John');
});
```

---

## 6. 安全规范

### 密钥管理

```typescript
// ❌ 禁止
const API_KEY = 'YOUR_API_KEY_HERE';

// ✅ 正确: 使用环境变量
import { env } from '$env/dynamic/private';
const API_KEY = env.API_KEY;
if (!API_KEY) {
  throw new Error('API_KEY not set');
}
```

---

## 7. 质量检查清单

### 代码质量

- [ ] ESLint 通过
- [ ] TypeScript 无错误
- [ ] 使用 Svelte 5 runes
- [ ] 无旧语法 (export let, $:)
- [ ] 无硬编码密钥

### 测试质量

- [ ] 核心组件测试覆盖 > 80%
- [ ] 所有测试通过
- [ ] E2E 测试覆盖核心流程
- [ ] Mock 使用正确

### 性能

- [ ] 使用 SSG/SSR
- [ ] 使用 lazy loading
- [ ] 避免不必要的重渲染

---

*本规范随 Svelte 生态演进持续更新。最后更新: 2026-07-17*
