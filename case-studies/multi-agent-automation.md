# 多 Agent 自动化工作流

## 背景

**项目**: 开源项目质量保证体系
**规模**: 3 个 Agent 协作
**目标**: 建立自动化的代码审查、测试生成、文档更新流程

---

## AI 协作过程

### 架构设计

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  代码审查    │ ──→ │  测试生成    │ ──→ │  文档更新    │
│  Agent      │     │  Agent      │     │  Agent      │
└─────────────┘     └─────────────┘     └─────────────┘
       │                   │                   │
       └───────────────────┴───────────────────┘
                           │
                    ┌──────▼──────┐
                    │   编排器     │
                    │ Orchestrator │
                    └─────────────┘
```

### Agent 1: 代码审查 Agent

**职责**: 分析代码变更，识别问题

**Prompt 模板**:
```
你是一位代码审查专家。请审查以下代码变更：

变更文件：{file_path}
变更内容：{diff}

请从以下维度审查：
1. 代码质量 (可读性、可维护性)
2. 潜在 Bug
3. 性能问题
4. 安全风险

输出格式：
{
  "issues": [...],
  "severity": "high|medium|low",
  "suggestions": [...]
}
```

**实现**:
```python
class CodeReviewAgent:
    def __init__(self, llm):
        self.llm = llm
    
    async def review(self, diff: str, file_path: str) -> dict:
        prompt = self.review_prompt.format(
            file_path=file_path,
            diff=diff
        )
        response = await self.llm.generate(prompt)
        return self.parse_response(response)
```

### Agent 2: 测试生成 Agent

**职责**: 根据代码变更生成测试

**Prompt 模板**:
```
基于以下代码变更，生成测试用例：

变更代码：{code}
代码审查结果：{review_result}

要求：
1. 覆盖正常流程
2. 覆盖边界条件
3. 覆盖错误场景
4. 使用 pytest 框架

输出格式：
{
  "test_cases": [
    {
      "name": "test_xxx",
      "code": "...",
      "coverage": "xxx"
    }
  ]
}
```

**实现**:
```python
class TestGenerationAgent:
    def __init__(self, llm):
        self.llm = llm
    
    async def generate_tests(self, code: str, review: dict) -> dict:
        prompt = self.test_prompt.format(
            code=code,
            review_result=json.dumps(review)
        )
        response = await self.llm.generate(prompt)
        return self.parse_response(response)
```

### Agent 3: 文档更新 Agent

**职责**: 根据代码变更更新文档

**Prompt 模板**:
```
根据以下代码变更，更新相关文档：

变更文件：{file_path}
变更内容：{diff}
变更说明：{description}

请更新：
1. API 文档 (如果有接口变更)
2. README (如果有使用方式变更)
3. CHANGELOG (记录变更)

输出格式：
{
  "updates": [
    {
      "file": "xxx.md",
      "content": "..."
    }
  ]
}
```

### 编排器

**职责**: 协调 3 个 Agent 的执行

```python
class WorkflowOrchestrator:
    def __init__(self, review_agent, test_agent, doc_agent):
        self.review_agent = review_agent
        self.test_agent = test_agent
        self.doc_agent = doc_agent
    
    async def run(self, diff: str, file_path: str):
        # 1. 代码审查
        review = await self.review_agent.review(diff, file_path)
        
        # 2. 生成测试 (依赖审查结果)
        tests = await self.test_agent.generate_tests(diff, review)
        
        # 3. 更新文档 (依赖审查结果)
        docs = await self.doc_agent.update(file_path, diff, review)
        
        return {
            "review": review,
            "tests": tests,
            "docs": docs
        }
```

---

## 效率对比

| 指标 | Before AI | After AI | 提升 |
|------|-----------|----------|------|
| 代码审查 | 2 小时/PR | 10 分钟/PR | 12x |
| 测试生成 | 4 小时/PR | 30 分钟/PR | 8x |
| 文档更新 | 1 小时/PR | 5 分钟/PR | 12x |
| **总时间** | **7 小时/PR** | **45 分钟/PR** | **9.3x** |

---

## 关键洞察

### 1. Agent 间的数据流设计

```
代码变更 → 审查结果 → 测试生成 → 文档更新
              ↓
         问题列表 → 人工确认 → 自动修复
```

### 2. 错误处理很重要

每个 Agent 都需要：
- 输入验证
- 输出解析
- 异常处理
- 重试机制

### 3. 人在回路中 (Human in the Loop)

- 关键决策需要人工确认
- 高风险操作需要人工审批
- Agent 输出需要人工验证

### 4. 渐进式自动化

```
阶段 1: Agent 辅助，人工决策
阶段 2: Agent 执行，人工审批
阶段 3: Agent 自动执行，异常时通知
```

---

## 适用场景

- ✅ 重复性工作流自动化
- ✅ 多步骤任务编排
- ✅ 质量保证流程
- ⚠️ 需要人工判断的场景
- ⚠️ 实时性要求高的场景

---

## 技术栈

- **AI 工具**: Claude API + OpenAI API
- **编排**: 自建 Python 编排器
- **消息队列**: Redis (任务分发)
- **存储**: PostgreSQL (结果存储)
