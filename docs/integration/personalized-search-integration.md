---
title: 个性化搜索集成
description: 如何使用 ai-navigation 的个性化搜索功能
category: 工具层
tags: ['AI', 'search', 'personalization']
difficulty: 进阶
reading_time: 8 分钟
updated: 2026-07-21
---

# 个性化搜索集成

> BM25 + 向量语义 + 用户画像的混合搜索。

---

## 技术栈

| 组件 | 技术 |
|------|------|
| 关键词搜索 | BM25 (TF-IDF 升级版) |
| 语义搜索 | sentence-transformers + cosine similarity |
| 混合融合 | Reciprocal Rank Fusion (RRF) |
| 同义词 | 中英文技术术语扩展 |
| 个性化 | 用户画像 + 协同过滤 |

## 搜索模式

```bash
# BM25 关键词搜索
python cli.py query "AI 协作" --mode bm25

# 向量语义搜索
python cli.py query "如何学习 AI" --mode vector

# 混合搜索 (推荐)
python cli.py query "AI 协作开发" --mode hybrid
```

## 个性化推荐

```bash
# 基于用户角色推荐
python cli.py recommend --role "前端工程师" --experience "3年"

# 基于学习目标推荐
python cli.py recommend --goals "微服务,性能优化"
```

## 对话式问答

```python
from src.chat_interface import ChatInterface
from src.vector_search import VectorSearchEngine

engine = VectorSearchEngine()
# ... 加载文档 ...

chat = ChatInterface(engine)
result = chat.ask("如何用 AI 进行代码审查？")
print(result["answer"])
```

## 与知识库集成

- 从 `docs/` 构建向量索引
- 从 `case-studies/` 提取案例数据
- 行为数据存储在 `user_profiles.json`

## 相关资源

- [[../../examples/ai-navigation/README|导航系统示例]]
- [[efficiency/personalized-search|个性化搜索方法论]]
- [[tools/rag-for-developers|RAG 开发指南]]

---

*Last Updated: 2026-07-21*
