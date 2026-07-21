# AI Navigation

> 知识库智能 BM25 + 同义词扩展 + 协同过滤的 RAG 引擎。

---

## 定位

验证 `docs/efficiency/full-cycle-workflow` 中的知识产品化方法论和 `mindset/capability-model` 中的个性化推荐能力。

## 核心能力

| 功能 | 描述 |
|------|------|
| `build` | 从 Markdown 文档构建知识索引 (JSON) |
| `query` | 基于 BM25 的语义搜索 (支持交互模式) |
| `recommend` | 基于用户路径推荐 |
| `stats` | 知识库统计信息 |

## 技术栈

- **BM25 评分**: TF-IDF 升级版，支持 k1/b 参数调节
- **同义词扩展**: 中英文技术术语自动扩展
- **协同过滤**: 基于用户行为的相似用户推荐
- **中文分词**: jieba 分词 + 停用词过滤
- **行为追踪**: 用户搜索/浏览/反馈记录

## 快速开始

```bash
pip install -e .

# 构建索引
python cli.py build --repo-root ../../

# 查询
python cli.py query "如何学习 AI 协作开发"

# 交互模式
python cli.py query -i

# 个性化推荐
python cli.py recommend --role "前端工程师" --experience "3年"
```

## 测试

```bash
python -m pytest tests/ -v
# 17 tests passed
```

## 相关文档

- [[docs/mindset/capability-model|能力模型]]
- [[docs/efficiency/full-cycle-workflow|全周期工作流]]
