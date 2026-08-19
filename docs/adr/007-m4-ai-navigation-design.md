---
title: ADR-007: M4 AI 导航系统设计
description: ## 状态
category: 治理层
tags: ['AI', 'API', 'Python', 'ADR', 'm4']
difficulty: 进阶
reading_time: 10 分钟
updated: 2026-07-21
---

# ADR-007: M4 AI 导航系统设计

## 状态

待评审

## 背景

M4 里程碑目标是实现"知识产品化"，包括:
1. AI 导航: 基于知识库的对话式导师
2. 个性化路径: 基于用户背景推荐学习路径
3. 实时更新: 与 AI 工具生态同步

## 决策

### 1. AI 导航系统架构

采用 **RAG (Retrieval-Augmented Generation)** 架构:

```
用户问题
    ↓
问题理解 (Query Understanding)
    ↓
知识检索 (Knowledge Retrieval)
    ↓
上下文增强 (Context Augmentation)
    ↓
答案生成 (Answer Generation)
    ↓
引用追溯 (Citation Tracing)
```

### 2. 知识索引结构

```json
{
  "documents": [
    {
      "id": "doc-001",
      "type": "methodology",
      "category": "efficiency",
      "title": "全周期 AI 辅助开发工作流",
      "content": "...",
      "metadata": {
        "difficulty": "intermediate",
        "tools": ["Cursor", "Copilot", "Claude"],
        "reading_time": "15min"
      }
    },
    {
      "id": "case-001",
      "type": "case_study",
      "category": "web",
      "title": "电商平台重构",
      "content": "...",
      "metadata": {
        "efficiency_gain": "3x",
        "tools_used": ["Cursor"],
        "project_type": "Web 开发"
      }
    }
  ]
}
```

### 3. 个性化推荐算法

```python
def recommend_path(user_profile: dict) -> list[dict]:
    """
    基于用户背景推荐学习路径

    输入:
      user_profile = {
        "role": "前端工程师",
        "experience": "3年",
        "ai_tools": ["Cursor"],
        "goals": ["提升效率", "学习 RAG"]
      }

    输出:
      [
        {"step": 1, "doc_id": "doc-001", "reason": "基础工作流"},
        {"step": 2, "doc_id": "doc-015", "reason": "RAG 入门"},
        {"step": 3, "case_id": "case-005", "reason": "RAG 实战案例"}
      ]
    """
```

### 4. 技术选型

| 组件 | 选择 | 理由 |
|------|------|------|
| 向量数据库 | ChromaDB | 轻量、本地优先、易于部署 |
| Embedding | text-embedding-3-small | 成本低、性能好 |
| LLM | GPT-4o-mini / Claude 3.5 | 性价比高 |
| 前端 | Markdown + 静态站点 | 与现有文档兼容 |

### 5. API 设计

```python
# 查询接口
POST / api / v1 / query
{"question": "如何用 Cursor 重构遗留代码?", "context": {"user_role": "后端工程师", "experience": "5年"}}

# 响应
{
    "answer": "根据案例库，推荐以下步骤...",
    "citations": [{"doc_id": "case-003", "title": "Cursor 重构遗留代码", "relevance": 0.95}],
    "follow_up": ["如何评估重构效果?", "有哪些避坑指南?"],
}
```

## 实现计划

### Phase 1: 基础 RAG (2 周)
- [ ] 构建知识索引
- [ ] 实现基础检索
- [ ] 集成 LLM 生成

### Phase 2: 个性化 (2 周)
- [ ] 用户画像模型
- [ ] 推荐算法
- [ ] 学习路径生成

### Phase 3: 交互优化 (2 周)
- [ ] 对话管理
- [ ] 引用追溯
- [ ] 反馈收集

## 后果

### 正面
- 用户可快速找到所需知识
- 个性化推荐提升学习效率
- 知识库价值最大化

### 负面
- 需要维护向量数据库
- LLM 调用成本
- 需要持续更新知识索引

### 风险
- 检索质量依赖知识库质量
- LLM 可能产生幻觉
- 需要定期评估和优化

## 验收标准

1. 检索准确率 ≥ 80%
2. 用户满意度 ≥ 4.0/5.0
3. 响应时间 < 3 秒
4. 支持 10+ 并发用户
