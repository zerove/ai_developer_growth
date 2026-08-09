---
title: Vue Governance Rules
description: > 适用于 Vue 项目的 AI Agent 开发规范。
category: 工具层
tags: ['AI', 'API', '测试', 'TypeScript', 'Vue']
difficulty: 高级
reading_time: 10 分钟
updated: 2026-07-21
---

# Vue Governance Rules

> 适用于 Vue 项目的 AI Agent 开发规范。

---

## 1. 组件规范

### Composition API 优先

```vue
<script setup lang="ts">
// ✅ 正确: Composition API
interface Props {
  user: User;
  onSelect: (user: User) => void;
}

const props = defineProps<Props>();

function handleClick() {
  props.onSelect(props.user);
}
</script>

<template>
  <div @click="handleClick">
    <h3>{{ user.name }}</h3>
  </div>
</template>
```

### Options API (仅在必要时)

```vue
<script lang="ts">
// ❌ 禁止: 除非维护旧代码
export default defineComponent({
  props: {
    user: { type: Object, required: true },
  },
  methods: {
    handleClick() {
      this.$emit('select', this.user);
    },
  },
});
</script>
```

---

## 2. 响应式系统

### ref vs reactive

```vue
<script setup lang="ts">
// ✅ 正确: 使用 ref
const count = ref(0);
const user = ref<User | null>(null);

// ✅ 正确: 使用 reactive (复杂对象)
const state = reactive({
  items: [],
  loading: false,
});

// ❌ 禁止: 不必要的 reactive
const name = reactive('hello');  // 应该用 ref
</script>
```

### computed

```vue
<script setup lang="ts">
// ✅ 正确
const fullName = computed(() => `${firstName.value} ${lastName.value}`);

// ❌ 禁止: 在 computed 中修改状态
const bad = computed(() => {
  count.value++;  // 副作用!
  return count.value;
});
</script>
```

---

## 3. 组件通信

### Props

```vue
<!-- ✅ 正确: 显式声明 -->
<script setup lang="ts">
interface Props {
  user: User;
  onSelect?: (user: User) => void;
}

const props = withDefaults(defineProps<Props>(), {
  onSelect: () => {},
});
</script>
```

### Emits

```vue
<!-- ✅ 正确: 显式声明 -->
<script setup lang="ts">
const emit = defineEmits<{
  select: [user: User];
  delete: [id: string];
}>();

function handleSelect() {
  emit('select', user);
}
</script>
```

### Provide/Inject

```vue
<!-- ✅ 正确: 跨层级通信 -->
<!-- Parent.vue -->
<script setup lang="ts">
provide('user', user);
</script>

<!-- Child.vue -->
<script setup lang="ts">
const user = inject('user');
</script>
```

---

## 4. 状态管理

### Pinia

```typescript
// ✅ 正确: 使用 Pinia
export const useUserStore = defineStore('user', () => {
  const user = ref<User | null>(null);
  const loading = ref(false);

  async function fetchUser(id: string) {
    loading.value = true;
    try {
      user.value = await api.getUser(id);
    } finally {
      loading.value = false;
    }
  }

  return { user, loading, fetchUser };
});
```

### 禁止行为

```typescript
// ❌ 禁止: 全局状态
window.__USER__ = user;

// ❌ 禁止: EventBus
const bus = new Vue();
bus.$emit('user-updated', user);
```

---

## 5. 测试规范

### Vitest + Vue Test Utils

```typescript
import { mount } from '@vue/test-utils';
import { describe, it, expect } from 'vitest';
import UserCard from './UserCard.vue';

describe('UserCard', () => {
  it('renders user name', () => {
    const wrapper = mount(UserCard, {
      props: { user: { id: '1', name: 'John' } },
    });
    expect(wrapper.text()).toContain('John');
  });

  it('emits select event', async () => {
    const wrapper = mount(UserCard, {
      props: { user: { id: '1', name: 'John' } },
    });

    await wrapper.trigger('click');
    expect(wrapper.emitted('select')).toHaveLength(1);
  });
});
```

---

## 6. 项目结构

```
project/
├── src/
│   ├── components/
│   │   ├── UserCard/
│   │   │   ├── UserCard.vue
│   │   │   ├── UserCard.test.ts
│   │   │   └── index.ts
│   ├── composables/
│   ├── stores/
│   ├── services/
│   └── App.vue
├── package.json
└── README.md
```

---

## 7. 安全规范

### XSS 防护

```vue
<!-- ❌ 禁止: 直接插入 HTML -->
<div v-html="userContent"></div>

<!-- ✅ 正确: Vue 自动转义 -->
<div>{{ userContent }}</div>
```

### 密钥管理

```typescript
// ❌ 禁止
const API_KEY = 'YOUR_API_KEY_HERE';

// ✅ 正确
const API_KEY = import.meta.env.VITE_API_KEY;
if (!API_KEY) {
  throw new Error('VITE_API_KEY not set');
}
```

---

## 8. 质量检查清单

### 代码质量

- [ ] ESLint 通过
- [ ] TypeScript 无错误
- [ ] 使用 Composition API
- [ ] 无 Options API (除非维护旧代码)
- [ ] 无硬编码密钥

### 测试质量

- [ ] 核心组件测试覆盖 > 80%
- [ ] 所有测试通过
- [ ] 使用 Vue Test Utils
- [ ] 无 snapshot 滥用

### 性能

- [ ] 使用 computed 缓存计算值
- [ ] 使用 shallowRef 减少响应式开销
- [ ] 无渲染中创建新对象

---

*本规范随 Vue 生态演进持续更新。最后更新: 2026-07-17*
