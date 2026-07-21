# 文档元数据规范

> 为所有文档添加标准化元数据，便于检索和分类

---

## 元数据格式

每个文档应在开头添加 YAML frontmatter:

```yaml
---
title: 文档标题
description: 一句话描述
category: 认知层|学习层|效率层|工具层|治理层
tags: [标签1, 标签2, 标签3]
difficulty: 入门|基础|进阶|高级|专家
reading_time: 5 分钟
prerequisites: [前置文档1, 前置文档2]
related: [相关文档1, 相关文档2]
updated: YYYY-MM-DD
author: 作者名
---
```

---

## 元数据字段说明

### 必填字段

| 字段 | 说明 | 示例 |
|------|------|------|
| `title` | 文档标题 | "AI 学习法" |
| `description` | 一句话描述 (50 字内) | "如何高效学习 AI 技术" |
| `category` | 文档分类 | "学习层" |
| `tags` | 标签列表 | ["AI", "学习方法", "效率"] |
| `difficulty` | 难度等级 | "进阶" |

### 可选字段

| 字段 | 说明 | 示例 |
|------|------|------|
| `reading_time` | 预计阅读时间 | "10 分钟" |
| `prerequisites` | 前置知识 | ["产品思维", "独立开发"] |
| `related` | 相关文档 | ["知识内化", "Prompt 工程"] |
| `updated` | 最后更新日期 | "2026-07-21" |
| `author` | 作者 | "Jcode" |

---

## 分类体系

### 认知层 (Mindset)

- 产品思维
- 独立开发者
- 市场发布
- 商业模式

### 学习层 (Learning)

- AI 学习法
- 知识内化
- Prompt 工程

### 效率层 (Efficiency)

- 全周期工作流
- 自动化修复
- 代码审查
- 测试策略

### 工具层 (Tools)

- 工具矩阵
- IDE 实践
- 模型选择

### 治理层 (Governance)

- 代码规范
- 安全规范
- 架构规范

---

## 标签体系

### 技术标签

- `python`, `javascript`, `typescript`, `rust`, `go`
- `react`, `vue`, `angular`, `svelte`
- `fastapi`, `django`, `flask`, `express`
- `docker`, `kubernetes`, `aws`, `gcp`

### 概念标签

- `ai`, `llm`, `rag`, `embedding`
- `microservices`, `api`, `database`
- `testing`, `ci/cd`, `devops`
- `security`, `performance`, `monitoring`

### 场景标签

- `beginner`, `intermediate`, `advanced`
- `tutorial`, `guide`, `reference`
- `case-study`, `best-practice`

---

## 难度等级

| 等级 | 说明 | 目标读者 |
|------|------|----------|
| **入门** | 零基础可读 | 初学者 |
| **基础** | 需要基本编程知识 | 初级开发者 |
| **进阶** | 需要项目经验 | 中级开发者 |
| **高级** | 需要架构经验 | 高级开发者 |
| **专家** | 需要深度专业知识 | 架构师/专家 |

---

## 示例

### 示例 1: AI 学习法

```yaml
---
title: AI 学习法
description: 如何高效学习 AI 技术的方法论
category: 学习层
tags: [ai, learning, efficiency, methodology]
difficulty: 基础
reading_time: 10 分钟
prerequisites: [产品思维]
related: [知识内化, Prompt 工程]
updated: 2026-07-21
author: Jcode
---
```

### 示例 2: 微服务架构

```yaml
---
title: 微服务架构设计
description: 微服务架构的设计原则和实践
category: 效率层
tags: [microservices, architecture, design, scalability]
difficulty: 高级
reading_time: 15 分钟
prerequisites: [全周期工作流, API 设计]
related: [容器化部署, 服务网格]
updated: 2026-07-21
author: Jcode
---
```

---

## 自动化检查

使用脚本检查元数据完整性:

```bash
# 检查所有文档是否有元数据
python tools/scripts/check_metadata.py

# 检查元数据格式
python tools/scripts/validate_metadata.py

# 生成元数据报告
python tools/scripts/metadata_report.py
```

---

*最后更新: 2026-07-21*
