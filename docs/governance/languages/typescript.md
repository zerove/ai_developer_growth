---
title: TypeScript Governance Rules
description: > 适用于 TypeScript 项目的 AI Agent 开发规范。
category: 治理层
tags: ['AI', 'API', '测试', 'SQL', 'TypeScript']
difficulty: 高级
reading_time: 10 分钟
updated: 2026-07-21
---

# TypeScript Governance Rules

> 适用于 TypeScript 项目的 AI Agent 开发规范。

---

## 1. 代码规范

### 格式化

- **工具**: `prettier`
- **配置**: 使用项目 `.prettierrc`
- **行宽**: 80 字符
- **引号**: 双引号
- **分号**: 始终使用

### Linting

- **工具**: `eslint`
- **规则**: 启用 `@typescript-eslint` 推荐规则
- **类型检查**: `tsc --noEmit`

### 命名规范

```typescript
// ✅ 正确
interface UserService { ... }
function getUser(id: string): User { ... }
const MAX_RETRIES = 3;

// ❌ 禁止
interface userService { ... }  // 应为 PascalCase
function GetUser(id: string) { ... }  // 应为 camelCase
```

---

## 2. 错误处理

### 自定义错误类型

```typescript
class AppError extends Error {
  constructor(
    message: string,
    public code: string,
    public statusCode: number = 500
  ) {
    super(message);
    this.name = "AppError";
  }
}

class ValidationError extends AppError {
  constructor(
    public field: string,
    message: string
  ) {
    super(message, "VALIDATION_ERROR", 400);
    this.name = "ValidationError";
  }
}

class NotFoundError extends AppError {
  constructor(
    resource: string,
    id: string
  ) {
    super(`${resource} with id ${id} not found`, "NOT_FOUND", 404);
    this.name = "NotFoundError";
  }
}
```

### 禁止行为

```typescript
// ❌ 禁止: 空 catch
try {
  await doSomething();
} catch (e) {
  // 忽略错误
}

// ❌ 禁止: 不检查 null
function process(data: Data | null) {
  return data.value;  // 可能 null!
}

// ✅ 正确
function process(data: Data | null): string {
  if (data === null) {
    throw new NotFoundError("Data", "unknown");
  }
  return data.value;
}
```

---

## 3. 类型安全

### 严格类型

```typescript
// ❌ 禁止: 使用 any
function process(data: any): any {
  return data.key;
}

// ✅ 正确
function process(data: Record<string, unknown>): string {
  return String(data.key ?? "");
}

// ❌ 禁止: 使用 @ts-ignore
// @ts-ignore
const result = riskyOperation();

// ✅ 正确: 使用类型守卫
function isString(value: unknown): value is string {
  return typeof value === "string";
}

if (isString(value)) {
  // value 现在是 string 类型
}
```

### 泛型

```typescript
// ✅ 正确
interface Repository<T> {
  get(id: string): Promise<T>;
  create(entity: T): Promise<T>;
  update(id: string, entity: Partial<T>): Promise<T>;
}

class UserRepository implements Repository<User> {
  async get(id: string): Promise<User> {
    // 实现
  }

  async create(entity: User): Promise<User> {
    // 实现
  }

  async update(id: string, entity: Partial<User>): Promise<User> {
    // 实现
  }
}
```

---

## 4. 异步编程

### async/await

```typescript
// ✅ 正确
async function fetchData(url: string): Promise<Data> {
  const response = await fetch(url);
  if (!response.ok) {
    throw new AppError("Fetch failed", "FETCH_ERROR", response.status);
  }
  return response.json();
}

// ✅ 正确: 并发执行
async function processConcurrently() {
  const results = await Promise.all([
    processItem(1),
    processItem(2),
    processItem(3),
  ]);
  return results;
}
```

### 禁止行为

```typescript
// ❌ 禁止: .then() 链
fetch(url)
  .then(response => response.json())
  .then(data => process(data))
  .catch(error => handleError(error));

// ✅ 正确
async function example() {
  try {
    const response = await fetch(url);
    const data = await response.json();
    await process(data);
  } catch (error) {
    handleError(error);
  }
}
```

---

## 5. 测试规范

### Jest 结构

```typescript
import { UserService } from "./user.service";
import { NotFoundError } from "../errors";

describe("UserService", () => {
  let service: UserService;

  beforeEach(() => {
    service = new UserService();
  });

  describe("getUser", () => {
    it("should return user when found", async () => {
      const user = await service.getUser("123");
      expect(user.id).toBe("123");
    });

    it("should throw NotFoundError when not found", async () => {
      await expect(service.getUser("nonexistent"))
        .rejects
        .toThrow(NotFoundError);
    });
  });
});
```

### Mock 规范

```typescript
// ✅ 正确: 使用 jest.mock
jest.mock("./database", () => ({
  query: jest.fn(),
}));

// ❌ 禁止: 手动创建 mock
const mockDb = {
  query: () => ({ rows: [] }),
};
```

---

## 6. 项目结构

```
project/
├── src/
│   ├── index.ts
│   ├── models/
│   ├── services/
│   ├── repositories/
│   └── utils/
├── tests/
│   ├── unit/
│   └── integration/
├── tsconfig.json
├── package.json
└── README.md
```

### 依赖管理

- **工具**: `npm` 或 `pnpm`
- **锁定**: 使用 `package-lock.json` 或 `pnpm-lock.yaml`
- **版本**: 使用语义化版本

---

## 7. Node.js 特定

### 文件操作

```typescript
import { readFile, writeFile } from "fs/promises";

// ✅ 正确: 使用 promise API
async function readConfig(): Promise<Config> {
  const data = await readFile("config.json", "utf-8");
  return JSON.parse(data);
}

// ❌ 禁止: 同步 API
function readConfigSync(): Config {
  const data = fs.readFileSync("config.json", "utf-8");
  return JSON.parse(data);
}
```

### 环境变量

```typescript
// ❌ 禁止
const API_KEY = "YOUR_API_KEY_HERE";

// ✅ 正确
const API_KEY = process.env.API_KEY;
if (!API_KEY) {
  throw new AppError("API_KEY environment variable not set", "CONFIG_ERROR");
}
```

---

## 8. React 特定

### 组件规范

```typescript
// ✅ 正确: 使用函数组件
interface UserCardProps {
  user: User;
  onSelect: (user: User) => void;
}

export function UserCard({ user, onSelect }: UserCardProps) {
  return (
    <div onClick={() => onSelect(user)}>
      <h3>{user.name}</h3>
    </div>
  );
}

// ❌ 禁止: 类组件 (除非需要 lifecycle)
class UserCard extends React.Component<UserCardProps> {
  render() {
    return (
      <div onClick={() => this.props.onSelect(this.props.user)}>
        <h3>{this.props.user.name}</h3>
      </div>
    );
  }
}
```

### Hooks 规范

```typescript
// ✅ 正确
function useUser(id: string) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getUser(id)
      .then(setUser)
      .finally(() => setLoading(false));
  }, [id]);

  return { user, loading };
}

// ❌ 禁止: 在循环或条件中使用 hook
if (condition) {
  const [state, setState] = useState();  // 违反规则!
}
```

---

## 9. 安全规范

### SQL 注入防护

```typescript
// ❌ 禁止: 字符串拼接
const query = `SELECT * FROM users WHERE id = ${userId}`;

// ✅ 正确: 参数化查询
const query = "SELECT * FROM users WHERE id = ?";
const result = await db.query(query, [userId]);
```

### XSS 防护

```typescript
// ❌ 禁止: 直接插入 HTML
element.innerHTML = userInput;

// ✅ 正确: 使用 textContent
element.textContent = userInput;

// ✅ 正确: 使用框架的转义
<div>{userInput}</div>  // React 自动转义
```

---

## 10. 质量检查清单

### 代码质量

- [ ] `prettier --check` 通过
- [ ] `eslint` 无错误
- [ ] `tsc --noEmit` 无类型错误
- [ ] 无 `any` 类型
- [ ] 无 `@ts-ignore`/`@ts-expect-error`
- [ ] 无硬编码密钥

### 测试质量

- [ ] 核心逻辑测试覆盖 > 80%
- [ ] 所有测试通过
- [ ] 无空 catch 块
- [ ] Mock 使用正确

### 文档质量

- [ ] 所有公开函数有 JSDoc
- [ ] 复杂逻辑有注释
- [ ] README.md 已更新
- [ ] 示例代码可运行

---

*本规范随 TypeScript 生态演进持续更新。最后更新: 2026-07-17*
