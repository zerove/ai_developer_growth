# ADR-012: 向量 RAG 不作为 ai_developer_growth 检索核心

## 状态
接受（2026-08-28）

## 背景
ROADMAP P2-5 要求"若检索是核心场景则集成 chroma+embedding；
否则从愿景文档移除"。

本项目检索当前现状（2026-08-28 实测）：

1. **`tools/scripts/ai_native_mcp_server.py`**：知识库 MCP 服务，描述为
   "全文检索 docs/ 下知识库文档（BM25+同义词+jieba 中文分词）"。
   实测已能完成"返回标题、摘要、评分与路径"。
2. **`examples/ai-context-sync/`**：参考实现，含 BM25 + 向量双路，
   用于演示可行性而非主检索。
3. **案例研究 `case-studies/intelligent-customer-service.md`**：RAG
   出现是该案例的应用领域（NLP 智能客服），不是本项目架构。
4. **ROADMAP.md P0-1 检索声明**："BM25+同义词（已实现）；协同过滤/
   向量 RAG 见 examples 参考"——已与现状一致。

## 决策
**不在本项目主检索链集成向量 RAG。**

- 核心检索保持 `ai_native_mcp_server.py` 的 BM25+同义词+jieba
- `examples/ai-context-sync/` 保留向量 RAG 作为**参考实现**
- `docs/MOC.md` / `docs/case-studies/intelligent-customer-service.md`
  等"RAG"提及属于**案例研究**层面，不需修改
- 未来若用户体量 > 10000 文档或跨语种检索需求出现时，重新评估

## 后果

### 正面
- 检索依赖只有 `jieba`（Python 内置中文分词），无外部 embedding 服务
- 部署零成本（不需要 OPENAI_API_KEY / chromadb 服务）
- 维护简单，无需处理 embedding 模型升级、chroma 版本兼容等
- examples 已有可行参考，需要时可低风险接入

### 负面
- 跨语种检索能力弱（中文 BM25 对英文效果一般）
- 语义检索（"找相似问题"）能力缺失
- 大规模（万级以上）文档下 BM25 召回率开始下降

## 触发重新评估的条件
1. docs/ 文档数 > 10000
2. 出现 ≥ 3 起"BM25 召回率不足"的用户反馈
3. 项目需支持跨语种（中英混合）检索

## 相关决策
- ROADMAP P0-1：检索声明已与本 ADR 一致
- ROADMAP P2-5：完成（"决策 + 文档"——本文档即为决策产物）
- `examples/ai-context-sync/`：保留为向量 RAG 参考实现入口
