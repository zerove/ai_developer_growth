# TypeScript 语言规则

> 适用于 TypeScript 项目的 AI Agent 开发规则

---

## 代码风格

### 命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| 文件名 | kebab-case | `my-module.ts` |
| 函数名 | camelCase | `myFunction()` |
| 变量名 | camelCase | `myVariable` |
| 类名 | PascalCase | `MyClass` |
| 接口 | PascalCase | `MyInterface` |
| 类型 | PascalCase | `MyType` |
| 常量 | UPPER_SNAKE_CASE | `MAX_SIZE` |

### 导入顺序

```typescript
// 1. Node 内置模块
import fs from 'fs';
import path from 'path';

// 2. 第三方库
import express from 'express';
import { z } from 'zod';

// 3. 本地模块
import { myFunction } from './my-module';
```

---

## 错误处理

### 惯用模式

```typescript
// ✅ 正确
async function myFunction(): Promise<string> {
    try {
        const result = await doSomething();
        return result;
    } catch (error) {
        if (error instanceof SpecificError) {
            throw new MyError('Failed to do something', { cause: error });
        }
        throw error;
    }
}

// ❌ 错误
async function myFunction(): Promise<string> {
    try {
        const result = await doSomething();
        return result;
    } catch (error) {
        return '';
    }
}
```

---

## 测试

### 框架选择

| 框架 | 适用场景 |
|------|----------|
| Jest | 通用测试 |
| Vitest | 快速测试 |
| Playwright | E2E 测试 |

### 测试结构

```typescript
describe('myFunction', () => {
    it('should return correct result', () => {
        const result = myFunction(1, 2);
        expect(result).toBe(3);
    });

    it('should throw error for invalid input', () => {
        expect(() => myFunction(null, 2)).toThrow(MyError);
    });
});
```

---

## 文档

### JSDoc

```typescript
/**
 * 一句话描述函数功能。
 *
 * @param param1 - 参数1描述
 * @param param2 - 参数2描述
 * @returns 返回值描述
 * @throws MyError 当参数无效时
 */
function myFunction(param1: number, param2: string): boolean {
    return true;
}
```

---

## 工具配置

### ESLint

```json
// .eslintrc.json
{
    "extends": [
        "eslint:recommended",
        "typescript-eslint/recommended"
    ],
    "rules": {
        "@typescript-eslint/no-unused-vars": "error",
        "@typescript-eslint/explicit-function-return-type": "warn"
    }
}
```

### TypeScript

```json
// tsconfig.json
{
    "compilerOptions": {
        "target": "ES2022",
        "module": "ESNext",
        "strict": true,
        "esModuleInterop": true,
        "skipLibCheck": true
    }
}
```

---

## AI 生成代码反模式

> 以下是 AI 生成代码中最常见的问题，validate_language_rules.py 会自动检测

### 反模式 1: any 类型

```typescript
// ❌ 反模式: any disables type checking
function processData(data: any): any {
    return data.map((item: any) => item.value);
}

// ✅ 正确: use specific types
interface DataItem {
    value: string;
    id: number;
}
function processData(data: DataItem[]): string[] {
    return data.map(item => item.value);
}
```

### 反模式 2: 空 catch 块

```typescript
// ❌ 反模式: silent error swallowing
try {
    await apiCall();
} catch (error) {}

// ✅ 正确: handle or rethrow
try {
    await apiCall();
} catch (error) {
    if (error instanceof ApiError) {
        logger.error(`API failed: ${error.message}`);
        throw new ServiceError('API unavailable', { cause: error });
    }
    throw error;
}
```

### 反模式 3: innerHTML XSS

```typescript
// ❌ 反模式: innerHTML enables XSS
element.innerHTML = userInput;

// ✅ 正确: safe alternatives
element.textContent = userInput;  // plain text
element.appendChild(sanitizeHtml(userInput));  // sanitized HTML
```

### 反模式 4: var 声明

```typescript
// ❌ 反模式: var has function scope
var count = 0;

// ✅ 正确: const by default, let when needed
const count = 0;  // immutable
let index = 0;    // needs reassignment
```

### 反模式 5: 非类型化 mock

```typescript
// ❌ 反模式: untyped mock
const mockFn = jest.fn();

// ✅ 正确: typed mock
const mockFn = jest.fn<(arg: string) => Promise<boolean>>();
```

### 反模式 6: 非空断言

```typescript
// ❌ 反模式: non-null assertion bypasses null check
const user = getUser()!;
const name = user.name;

// ✅ 正确: proper null check
const user = getUser();
if (!user) throw new Error('User not found');
const name = user.name;
// or: const name = user?.name ?? 'Unknown';
```

---

## 量化阈值

| 指标 |
|------|------|------|
| 函数最大行数 | 40 | 超过应拆分 |
| 文件最大行数 | 400 | 超过应模块化 |
| 行最大长度 | 100 | 超过应换行 |
| 最大嵌套深度 | 4 | 超过应提取函数 |
| 最大函数参数 | 5 | 超过应使用接口 |
| 最大圈复杂度 | 10 | 超过应简化逻辑 |
| 测试覆盖率 | 80% | CI 门禁要求 |

---

*本规则适用于 TypeScript 项目的 AI Agent 开发。*
*验证工具: `python -m tools.scripts.validate_language_rules <path> --lang typescript`*
