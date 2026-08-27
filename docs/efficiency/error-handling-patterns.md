---
title: 错误处理模式 (Error Handling Patterns)
description: > 统一的错误处理策略与最佳实践。
category: 效率层
tags: ['AI', 'error', 'TypeScript', 'handling', '数据库']
difficulty: 基础
reading_time: 10 分钟
updated: 2026-07-21
---

# 错误处理模式 (Error Handling Patterns)

> 统一的错误处理策略与最佳实践。

---

## 1. 错误处理原则

**核心理念**: 错误不是异常，而是**预期的业务状态**。

错误分类:
```
错误类型
├── 可恢复错误 (用户可操作)
├── 不可恢复错误 (系统级)
└── 业务错误 (业务规则违反)
```

---

## 2. 错误分类与处理策略

### 2.1 可恢复错误

**特征**: 用户可以修复并重试

```typescript
// 错误类型定义
class ValidationError extends Error {
  constructor(
    message: string,
    public field: string,
    public code: string
  ) {
    super(message);
    this.name = 'ValidationError';
  }
}

// 使用示例
function validateEmail(email: string): void {
  if (!email.includes('@')) {
    throw new ValidationError(
      'Invalid email format',
      'email',
      'INVALID_FORMAT'
    );
  }
}

// 前端处理
try {
  await createUser(userData);
} catch (error) {
  if (error instanceof ValidationError) {
    // 显示给用户，让他们修复
    showError(error.field, error.message);
  }
}
```

### 2.2 不可恢复错误

**特征**: 系统级错误，需要开发者介入

```typescript
class SystemError extends Error {
  constructor(
    message: string,
    public code: string,
    public retryable: boolean = false
  ) {
    super(message);
    this.name = 'SystemError';
  }
}

// 使用示例
async function connectDatabase(): Promise<Connection> {
  try {
    return await db.connect();
  } catch (error) {
    throw new SystemError(
      'Database connection failed',
      'DB_CONNECTION_FAILED',
      true  // 可重试
    );
  }
}

// 重试逻辑
async function withRetry<T>(
  fn: () => Promise<T>,
  maxRetries: number = 3
): Promise<T> {
  for (let i = 0; i < maxRetries; i++) {
    try {
      return await fn();
    } catch (error) {
      if (error instanceof SystemError && error.retryable) {
        if (i === maxRetries - 1) throw error;
        await sleep(1000 * Math.pow(2, i)); // 指数退避
      } else {
        throw error;
      }
    }
  }
  throw new Error('Max retries exceeded');
}
```

### 2.3 业务错误

**特征**: 业务规则违反，不是真正的错误

```typescript
class BusinessError extends Error {
  constructor(
    message: string,
    public businessRule: string,
    public suggestions: string[]
  ) {
    super(message);
    this.name = 'BusinessError';
  }
}

// 使用示例
function transferMoney(from: Account, to: Account, amount: number): void {
  if (from.balance < amount) {
    throw new BusinessError(
      'Insufficient balance',
      'INSUFFICIENT_BALANCE',
      [
        'Deposit more funds',
        'Transfer a smaller amount',
        'Use a different account'
      ]
    );
  }
  // 执行转账...
}
```

---

## 3. 错误处理模式

### 3.1 Result 模式 (推荐)

```typescript
type Result<T, E = Error> =
  | { success: true; data: T }
  | { success: false; error: E };

// 使用示例
function parseJSON<T>(json: string): Result<T, string> {
  try {
    return { success: true, data: JSON.parse(json) };
  } catch (error) {
    return { success: false, error: 'Invalid JSON' };
  }
}

// 调用方处理
const result = parseJSON<User>(userJson);
if (result.success) {
  // result.data 是 User 类型
  await processUser(result.data);
} else {
  // result.error 是 string 类型
  showError(result.error);
}
```

### 3.2 Error Boundary 模式 (React)

```typescript
class ErrorBoundary extends React.Component<
  { children: React.ReactNode },
  { hasError: boolean; error?: Error }
> {
  state = { hasError: false, error: undefined };

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    // 上报错误
    logError(error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return <ErrorFallback error={this.state.error} />;
    }
    return this.props.children;
  }
}
```

### 3.3 全局错误处理

```typescript
// 未捕获异常处理
process.on('uncaughtException', (error) => {
  console.error('Uncaught Exception:', error);
  // 上报错误
  reportError(error);
  // 优雅退出
  process.exit(1);
});

// 未处理的 Promise 拒绝
process.on('unhandledRejection', (reason, promise) => {
  console.error('Unhandled Rejection:', reason);
  reportError(reason);
});

// 前端全局错误处理
window.addEventListener('error', (event) => {
  reportError(event.error);
});

window.addEventListener('unhandledrejection', (event) => {
  reportError(event.reason);
});
```

---

## 4. 错误恢复策略

| 策略 | 适用场景 | 实现方式 |
|------|----------|----------|
| **重试** | 网络请求、临时故障 | 指数退避 + 最大重试次数 |
| **降级** | 非核心功能不可用 | 使用备用方案 |
| **熔断** | 连续失败 | 暂停请求，定时恢复 |
| **回滚** | 数据操作失败 | 事务回滚 |

---

**📂 导航**
- [[../MOC|⬅️ 返回知识地图]]
- **相关**: [[efficiency/debugging-workflow|调试工作流]] | [[efficiency/anti-patterns|反模式]]
---

## 导航

**分类**: 效率层

**相关文档**:

- [[docs/efficiency/full-cycle-workflow|全周期工作流]]
- [[docs/efficiency/automated-bug-fixing|自动化修复]]
- [[docs/efficiency/anti-patterns|反模式]]
- [[docs/efficiency/context-engineering|上下文工程]]
- [[docs/efficiency/token-optimization|Token 优化]]
