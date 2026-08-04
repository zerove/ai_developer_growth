---
title: AI 辅助机器学习
description: 使用 AI 工具构建机器学习模型
category: 效率层
tags: [AI, 机器学习, MLOps]
difficulty: 高级
reading_time: 15 分钟
updated: 2026-07-21
---

# AI 辅助机器学习

## 核心原则

ML 开发 = 数据准备 + 模型训练 + 部署监控

## 开发流程

```
数据收集 → 数据清洗 → 特征工程 → 模型训练 → 评估优化 → 部署监控
```

## Prompt 技巧

### 1. 模型选择

```markdown
请推荐机器学习模型:
- 任务类型: 分类/回归/聚类
- 数据规模: 10 万行
- 特征数量: 50
- 性能要求: 高精度
```

### 2. 特征工程

```markdown
请生成特征工程:
- 数值特征: 标准化
- 类别特征: One-Hot
- 文本特征: TF-IDF
```

### 3. 模型优化

```markdown
请优化模型:
- 超参数调优
- 交叉验证
- 集成学习
```

## 工具选择

### 1. 传统 ML

```
Scikit-learn: 通用 ML 库
XGBoost: 梯度提升
LightGBM: 轻量梯度提升
```

### 2. 深度学习

```
PyTorch: 灵活易用
TensorFlow: 生产部署
Keras: 快速原型
```

### 3. AutoML

```
Auto-sklearn: 自动化 ML
H2O: 自动化平台
Google AutoML: 云服务
```

## 最佳实践

### 1. 数据管理

```
数据版本控制 → 数据质量检查 → 数据血缘
```

### 2. 实验管理

```
实验追踪 → 模型版本 → 超参数记录
```

### 3. MLOps

```
模型训练 → 模型注册 → 模型部署 → 模型监控
```

## 常见问题

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| 过拟合 | 数据不足 | 正则化 |
| 欠拟合 | 模型简单 | 增加复杂度 |
| 训练慢 | 数据量大 | 分布式训练 |

## 效率提升

### 1. AutoML

使用 AutoML 自动化模型选择。

### 2. 迁移学习

使用预训练模型加速。

### 3. 实验追踪

使用 MLflow 追踪实验。

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
