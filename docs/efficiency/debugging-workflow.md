---
title: AI 辅助调试工作流 (Debugging Workflow)
description: > AI 驱动的系统化调试方法论。
category: 效率层
tags: ['AI', '测试', 'TypeScript', 'workflow', 'debugging']
difficulty: 初级
reading_time: 10 分钟
updated: 2026-07-21
---

# AI 辅助调试工作流 (Debugging Workflow)

> AI 驱动的系统化调试方法论。

---

## 1. 调试原则

**核心理念**: AI 辅助调试 ≠ 让 AI 修 Bug，而是**加速定位根因**。

调试流程:
```
复现问题 → 收集信息 → AI 分析 → 提出假设 → 验证假设 → 修复
    ↓           ↓          ↓          ↓          ↓       ↓
  最小复现   日志/堆栈   根因分析   多个假设   单元测试  最小修复
```

---

## 2. 调试工作流

### 2.1 第一步: 最小化复现

**原则**: 在让 AI 分析前，先最小化问题。

```bash
# 好: 最小复现用例
# 只保留核心代码，移除无关依赖
function reproduceBug() {
  // 最小输入
  const input = { email: 'test@example.com' };
  // 观察输出
  const result = validateEmail(input.email);
  console.log(result); // 期望: true, 实际: false
}
```

### 2.2 第二步: 收集上下文

**给 AI 的上下文**:
```markdown
## 问题描述
- 期望行为: validateEmail('test@example.com') 返回 true
- 实际行为: 返回 false
- 复现步骤: 运行 reproduceBug()

## 环境信息
- Node.js 版本: v20.10.0
- 操作系统: macOS 14.2
- 相关依赖: zod@3.22.4

## 错误日志
[粘贴完整错误日志]

## 相关代码
[粘贴最小复现代码]
```

### 2.3 第三步: AI 分析 Prompt

```
分析以下问题:

## 问题描述
[问题描述]

## 错误日志
[错误日志]

## 相关代码
[代码片段]

请提供:
1. 可能的根因 (按可能性排序)
2. 每个根因的验证方法
3. 推荐的修复方案
```

---

## 3. 常见 Bug 类型与 AI 策略

### 3.1 类型错误

**特征**: TypeScript 编译错误、类型不匹配

**AI Prompt**:
```
这个类型错误是什么原因？如何修复？

错误信息: [错误信息]
代码: [代码片段]
类型定义: [类型定义]
```

### 3.2 逻辑错误

**特征**: 代码运行但结果错误

**AI Prompt**:
```
这段代码的逻辑有什么问题？

期望行为: [期望]
实际行为: [实际]
代码: [代码]

请分析逻辑错误并提供修复方案。
```

### 3.3 异步错误

**特征**: Promise 未处理、竞态条件

**AI Prompt**:
```
这段异步代码有什么问题？

代码: [代码]

请分析:
1. 是否有未处理的 Promise
2. 是否有竞态条件
3. 如何正确处理异步
```

### 3.4 性能问题

**特征**: 响应慢、内存泄漏

**AI Prompt**:
```
这段代码有什么性能问题？

代码: [代码]
性能数据: [性能分析结果]

请分析:
1. 性能瓶颈在哪里
2. 如何优化
3. 优化后的预期效果
```

---

## 4. 调试工具链

### 4.1 日志分析

```bash
# 使用 AI 分析日志
cat app.log | ai-log-analyzer --detect-patterns

# 提取错误模式
ai-log-analyzer --extract-errors --group-by-type
```

### 4.2 堆栈分析

```bash
# AI 辅助堆栈分析
ai-stack-analyzer --stack "error.stack" --codebase ./src

# 自动定位问题代码
ai-stack-analyzer --auto-fix --dry-run
```

### 4.3 性能分析

```bash
# AI 性能分析
ai-profiler --file profile.log --suggest-optimizations

# 内存泄漏检测
ai-profiler --memory-leak --duration 60s
```

---

## 5. 调试反模式

| 反模式 | 问题 | 正确做法 |
|--------|------|----------|
| **直接让 AI 修** | 不理解根因 | 先自己分析，再让 AI 辅助 |
| **盲目尝试** | 随机修改 | 系统化假设验证 |
| **忽略日志** | 信息不足 | 完整收集上下文 |
| **不复现** | 无法验证 | 最小化复现问题 |

---

**📂 导航**
- [[MOC|⬅️ 返回知识地图]]
- **相关**: [[efficiency/automated-bug-fixing|自动化修复]] | [[efficiency/anti-patterns|反模式]]
---

## 导航

**分类**: 效率层

**相关文档**:

- [[docs/efficiency/full-cycle-workflow|全周期工作流]]
- [[docs/efficiency/automated-bug-fixing|自动化修复]]
- [[docs/efficiency/anti-patterns|反模式]]
- [[docs/efficiency/context-engineering|上下文工程]]
- [[docs/efficiency/token-optimization|Token 优化]]
