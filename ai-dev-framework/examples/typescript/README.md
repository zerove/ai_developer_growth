# TypeScript 示例项目

这是一个最小化的 TypeScript 示例项目，展示如何使用 ai-dev-framework。

---

## 项目结构

```
typescript-example/
├── src/
│   └── math.ts           # 主模块
├── tests/
│   └── math.test.ts      # 测试文件
├── CLAUDE.md             # 项目规范
├── AGENTS.md             # Agent 索引
├── CONTEXT.md            # 项目上下文
├── package.json          # 项目配置
└── tsconfig.json         # TypeScript 配置
```

---

## 快速开始

```bash
# 安装依赖
npm install

# 运行测试
npm test

# 代码检查
npm run lint
```

---

## Agent 示例

### src/math.ts

```typescript
/**
 * 两个数相加。
 *
 * @param a - 第一个数
 * @param b - 第二个数
 * @returns 两数之和
 */
export function add(a: number, b: number): number {
    return a + b;
}
```

### tests/math.test.ts

```typescript
import { describe, it, expect } from 'vitest';
import { add } from '../src/math';

describe('add', () => {
    it('should return correct result', () => {
        expect(add(1, 2)).toBe(3);
    });

    it('should handle negative numbers', () => {
        expect(add(-1, 1)).toBe(0);
    });
});
```

---

## 质量门禁检查

```bash
# 检查代码质量
bash .ai-framework/quality-gates/scripts/check.sh typescript
```

---

*这是一个最小化的 TypeScript 示例项目。*
