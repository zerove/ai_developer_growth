---
title: AI 辅助技术选型
description: 使用 AI 工具进行技术选型决策
category: 效率层
tags: [AI, 技术选型, 架构决策]
difficulty: 中级
reading_time: 10 分钟
updated: 2026-07-21
---

# AI 辅助技术选型

## 核心原则

AI 选型 = 需求分析 + 方案对比 + 决策依据

## 选型流程

```
需求分析 → 方案收集 → 评估对比 → 决策验证 → 实施跟踪
```

## Prompt 技巧

### 1. 方案推荐

```markdown
请推荐技术方案:
- 场景: 高并发 Web 应用
- 需求: 1000 QPS，99.9% 可用性
- 约束: 团队熟悉 Python
```

### 2. 方案对比

```markdown
请对比技术方案:
- 方案 A: FastAPI + PostgreSQL
- 方案 B: Django + MySQL
- 对比维度: 性能、生态、学习成本
```

### 3. 选型报告

```markdown
请生成选型报告:
- 选型背景
- 候选方案
- 评估标准
- 推荐方案
- 风险分析
```

## 选型维度

### 1. 技术维度

```
性能 → 可扩展性 → 可维护性 → 生态系统
```

### 2. 团队维度

```
学习成本 → 开发效率 → 招聘难度 → 技术储备
```

### 3. 业务维度

```
业务匹配 → 迭代速度 → 成本控制 → 风险管理
```

## 决策框架

### 1. 评分矩阵

| 方案 | 性能 | 生态 | 成本 | 总分 |
|------|------|------|------|------|
| A | 9 | 8 | 7 | 8.0 |
| B | 7 | 9 | 8 | 8.0 |

### 2. 决策树

```
性能要求高?
├── 是 → 语言性能?
│   ├── 高 → Go/Rust
│   └── 中 → Java/Python
└── 否 → 开发效率?
    ├── 高 → Python/Node.js
    └── 中 → Java/C#
```

### 3. ADR (Architecture Decision Record)

```markdown
## ADR: 选择 FastAPI

### 状态
已批准

### 背景
需要高性能 Web 框架

### 决策
选择 FastAPI

### 原因
- 异步支持
- 自动文档
- 类型安全
```

## 最佳实践

### 1. 原型验证

```
PoC 开发 → 性能测试 → 团队评估
```

### 2. 渐进迁移

```
新功能试点 → 逐步迁移 → 全面切换
```

### 3. 技术债务

```
记录决策 → 定期评估 → 持续优化
```

## 效率提升

### 1. 模板化

建立选型报告模板。

### 2. 数据化

基于数据做决策。

### 3. 自动化

自动化评估流程。

---

*最后更新: 2026-07-21*

---

## 导航

**分类**: 效率层

**相关文档**:

- [[docs/efficiency/full-cycle-workflow|全周期工作流]]
- [[docs/efficiency/automated-bug-fixing|自动化修复]]
- [[docs/efficiency/anti-patterns|反模式]]
- [[docs/efficiency/context-engineering|上下文工程]]
- [[docs/efficiency/token-optimization|Token 优化]]
