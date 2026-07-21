---
title: JavaScript Governance Rules
description: > 适用于: JavaScript 项目 (Node.js, 浏览器, React, Vue, Angular 等)
category: 治理层
tags: ['AI', 'API', 'REST', 'SQL', 'TypeScript']
difficulty: 初级
reading_time: 10 分钟
updated: 2026-07-21
---

# JavaScript Governance Rules

> 适用于: JavaScript 项目 (Node.js, 浏览器, React, Vue, Angular 等)

---

## 1. 代码规范

### 格式化

```bash
# ESLint + Prettier
npx eslint --fix .
npx prettier --write .
```

### Linting

```json
{
  "extends": [
    "eslint:recommended",
    "plugin:@typescript-eslint/recommended",
    "plugin:react/recommended",
    "plugin:react-hooks/recommended",
    "prettier"
  ],
  "rules": {
    "no-unused-vars": "error",
    "no-console": "warn",
    "prefer-const": "error",
    "no-var": "error",
    "eqeqeq": ["error", "always"],
    "no-eval": "error",
    "no-implied-eval": "error"
  }
}
```

### 命名规范

```javascript
// ✅ 正确
const userName = "Alice";
const getMaxValue = () => {};
const UserCard = () => {};
const API_BASE_URL = "https://api.example.com";
const isValid = true;
const handleSubmit = () => {};

// ❌ 禁止
var user_name = "Alice";      // 应使用 camelCase
function get_max_value() {}   // 应使用 camelCase
function UserCard() {}        // 组件应使用 PascalCase
const api_base_url = "...";   // 常量应使用 UPPER_SNAKE_CASE
```

---

## 2. 错误处理

### 异常处理

```javascript
// ✅ 正确 - 使用 try/catch
async function fetchData(url) {
  try {
    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    return await response.json();
  } catch (error) {
    console.error("Failed to fetch:", error);
    throw error;
  }
}

// ✅ 正确 - 自定义错误类
class ValidationError extends Error {
  constructor(message, field) {
    super(message);
    this.name = "ValidationError";
    this.field = field;
  }
}

// ❌ 禁止
function fetchData(url) {
  return fetch(url)
    .then((res) => res.json())
    .catch(() => null); // 吞掉错误
}
```

### Promise 处理

```javascript
// ✅ 正确 - 始终处理 Promise 拒绝
const promise = fetchData();
promise.catch(handleError);

// ✅ 正确 - 使用 async/await
async function processData() {
  try {
    const data = await fetchData();
    return transform(data);
  } catch (error) {
    handleError(error);
  }
}

// ❌ 禁止 - 未处理的 Promise
const promise = fetchData();
// 忘记 .catch()
```

---

## 3. 安全性

### 输入验证

```javascript
// ✅ 正确 - 验证所有用户输入
function sanitizeInput(input) {
  if (typeof input !== "string") {
    throw new TypeError("Input must be a string");
  }
  return input
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

// ✅ 正确 - 使用参数化查询
const query = "SELECT * FROM users WHERE id = ?";
db.query(query, [userId]);

// ❌ 禁止 - SQL 注入
const query = `SELECT * FROM users WHERE id = ${userId}`;
```

### 敏感数据

```javascript
// ✅ 正确 - 环境变量
const apiKey = process.env.API_KEY;

// ❌ 禁止 - 硬编码
const apiKey = "sk-1234567890abcdef";
```

---

## 4. 异步编程

### Async/Await

```javascript
// ✅ 正确 - 使用 async/await
async function getUser(id) {
  const user = await db.users.findById(id);
  if (!user) {
    throw new NotFoundError("User not found");
  }
  return user;
}

// ✅ 正确 - 并行执行
async function getDashboard() {
  const [user, posts, notifications] = await Promise.all([
    getUser(),
    getPosts(),
    getNotifications(),
  ]);
  return { user, posts, notifications };
}

// ❌ 禁止 - 顺序执行不必要的异步操作
async function getDashboard() {
  const user = await getUser();
  const posts = await getPosts(); // 可以并行
  const notifications = await getNotifications(); // 可以并行
  return { user, posts, notifications };
}
```

---

## 5. 模块化

### ES Modules

```javascript
// ✅ 正确 - 使用 ES Modules
import { useState } from "react";
import { fetchData } from "./api.js";
export default MyComponent;

// ❌ 禁止 - CommonJS (新项目)
const React = require("react");
module.exports = MyComponent;
```

### 导出规范

```javascript
// ✅ 正确 - 命名导出
export const formatDate = (date) => {};
export const parseJSON = (str) => {};

// ✅ 正确 - 默认导出 (单个主要导出)
export default class UserService {}

// ❌ 禁止 - 导出太多内容
export { a, b, c, d, e, f, g }; // 应该重新组织
```

---

## 6. React/Vue 特定

### React 组件

```javascript
// ✅ 正确 - 函数组件 + Hooks
function UserCard({ user }) {
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    // 副作用
  }, [user.id]);

  if (loading) return <Spinner />;

  return (
    <div className="user-card">
      <h2>{user.name}</h2>
    </div>
  );
}

// ❌ 禁止 - Class 组件 (新项目)
class UserCard extends React.Component {
  // ...
}
```

### Vue 组件

```javascript
// ✅ 正确 - Composition API
export default {
  setup(props) {
    const count = ref(0);
    const doubled = computed(() => count.value * 2);

    return { count, doubled };
  },
};

// ❌ 禁止 - Options API (新项目)
export default {
  data() {
    return { count: 0 };
  },
  computed: {
    doubled() {
      return this.count * 2;
    },
  },
};
```

---

## 7. 测试

```javascript
// ✅ 正确 - 单元测试
describe("UserService", () => {
  it("should create user with valid data", async () => {
    const user = await createUser({ name: "Alice" });
    expect(user.name).toBe("Alice");
    expect(user.id).toBeDefined();
  });

  it("should throw on invalid email", async () => {
    await expect(createUser({ email: "invalid" })).rejects.toThrow(
      ValidationError
    );
  );
});
```

---

## 8. 性能

### 懒加载

```javascript
// ✅ 正确 - 动态导入
const LazyComponent = React.lazy(() => import("./LazyComponent"));

// ✅ 正确 - 路由懒加载
const Dashboard = React.lazy(() => import("./pages/Dashboard"));
```

### 防抖/节流

```javascript
// ✅ 正确 - 搜索输入防抖
const debouncedSearch = useMemo(
  () => debounce((query) => searchAPI(query), 300),
  []
);

// ❌ 禁止 - 每次输入都请求
const handleSearch = (query) => searchAPI(query);
```

---

## 9. 禁止行为

| 行为 | 原因 |
|------|------|
| 使用 `var` | 使用 `const` 或 `let` |
| 使用 `==` | 使用 `===` |
| 使用 `eval()` | 安全风险 |
| 使用 `arguments` | 使用 rest 参数 |
| 使用 `with` 语句 | 代码混乱 |
| 使用 `delete` 删除数组 | 性能问题 |
| 使用 `new Array()` | 使用数组字面量 |
| 使用 `typeof` 比较 `null` | `null` 类型是 `"object"` |
| 使用 `void 0` | 使用 `undefined` |

---

*最后更新: 2026-07-21*
