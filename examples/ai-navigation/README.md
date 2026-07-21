# AI Navigation System

基于 RAG 的 AI 知识导航系统，为 AI Developer Growth 知识库提供智能查询和个性化学习路径推荐。

## 功能

1. **知识索引构建** - 自动索引所有文档、案例研究和 ADR
2. **RAG 查询引擎** - 基于检索增强生成的回答系统
3. **个性化推荐** - 根据用户角色和目标推荐学习路径

## 架构

```
ai-navigation/
├── src/
│   ├── __init__.py
│   ├── knowledge_index.py  # 知识索引构建器
│   ├── rag_engine.py       # RAG 查询引擎
│   └── path_recommender.py # 个性化路径推荐
├── tests/
│   └── test_navigation.py
├── main.py                 # 主入口
└── requirements.txt
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 构建索引

```bash
python main.py index
```

### 3. 运行演示

```bash
python main.py demo
```

### 4. 交互模式

```bash
python main.py interactive
```

## 使用示例

### 查询知识

```python
from src.knowledge_index import IndexBuilder
from src.rag_engine import RAGEngine, QueryContext

# 构建索引
builder = IndexBuilder(".")
index = builder.build()

# 创建 RAG 引擎
engine = RAGEngine(index)

# 查询
result = engine.query(QueryContext(question="如何用 Cursor 重构代码?"))
print(result.answer)
print(result.citations)
```

### 推荐学习路径

```python
from src.path_recommender import PathRecommender, UserProfile

# 创建推荐器
recommender = PathRecommender(index)

# 用户画像
user = UserProfile(
    role="前端工程师",
    experience="2年",
    current_tools=["Cursor", "Copilot"],
    goals=["提升效率", "学习 RAG"]
)

# 获取推荐
paths = recommender.recommend(user)
for path in paths:
    print(f"{path.name}: {[s.title for s in path.steps]}")
```

## 数据流

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

## 测试

```bash
pytest tests/ -v
```

## 扩展

### 添加向量搜索

当前使用关键词搜索，可通过以下方式扩展为向量搜索:

1. 安装 `chromadb` 或 `faiss`
2. 使用 OpenAI/Claude 生成 embedding
3. 替换 `KnowledgeIndex.search()` 实现

### 集成 LLM

当前使用模板生成答案，可通过以下方式集成 LLM:

1. 安装 `openai` 或 `anthropic`
2. 将检索结果作为 context
3. 调用 LLM 生成答案

## 相关文档

- [ADR-007: M4 AI 导航系统设计](../../docs/adr/ADR-007-m4-ai-navigation-design.md)
- [RAG 开发者指南](../../docs/tools/rag-for-developers.md)
