# Vue 3 开发规则

> 基于 TypeScript 的 Vue 3 开发标准

---

## 核心约定

### 文件组织

```
src/
├── components/      # 通用组件
├── composables/     # 组合式 API
├── views/           # 页面视图
├── router/          # 路由配置
├── stores/          # Pinia 状态管理
├── api/             # API 请求
├── types/           # 类型定义
└── utils/           # 工具函数
```

### 组件命名

- **单文件组件**: `PascalCase.vue`
- **Composable**: `camelCase.ts` (useAuth.ts)
- **Store**: `camelCase.ts` (userStore.ts)
- **类型文件**: `camelCase.types.ts`

---

## Composition API 规范

```vue
<script setup lang="ts">
// ✅ 推荐的 setup 模式
import { ref, computed, onMounted } from 'vue'

// 状态
const count = ref(0)
const doubled = computed(() => count.value * 2)

// 方法
function increment() {
  count.value++
}

// 生命周期
onMounted(() => {
  console.log('mounted')
})
</script>

<template>
  <button @click="increment">{{ count }} (x2 = {{ doubled }})</button>
</template>

<style scoped>
/* 默认使用 scoped 样式 */
</style>
```

---

## 质量门禁

### Lint

```bash
# 检查
npx eslint src/ --ext .vue,.ts
npx vue-tsc --noEmit

# 格式化
npx prettier --check src/
```

### 测试

```bash
# 组件测试
npx vitest run

# 端到端
npx cypress run
```

---

## Composable 模式

```ts
// composables/useCounter.ts
export function useCounter(initial = 0) {
  const count = ref(initial)

  function increment() {
    count.value++
  }

  function decrement() {
    count.value--
  }

  return {
    count: readonly(count),
    increment,
    decrement
  }
}
```

---

## 状态管理

```ts
// stores/user.ts (Pinia)
import { defineStore } from 'pinia'

export const useUserStore = defineStore('user', () => {
  const user = ref<User | null>(null)
  const token = ref<string | null>(null)

  async function login(credentials: Credentials) {
    const { user: u, token: t } = await api.login(credentials)
    user.value = u
    token.value = t
  }

  return { user, token, login }
})
```

---

## 常用依赖

| 用途 | 推荐包 |
|------|--------|
| 路由 | vue-router v4 |
| 状态管理 | pinia |
| 数据获取 | @tanstack/vue-query |
| 表单 | vee-validate + zod |
| UI 组件 | primevue / naive-ui |
| 样式 | tailwindcss / unocss |
