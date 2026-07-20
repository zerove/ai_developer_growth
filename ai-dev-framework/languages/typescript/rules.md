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

*本规则适用于 TypeScript 项目的 AI Agent 开发。*
