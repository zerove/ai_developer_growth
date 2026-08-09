---
title: "案例研究：构建 AI 驱动的任务优先级排序工具"
description: "在本案例中，我们将演示如何利用"全周期 AI 工作流"快速从 0 到 1 构建一个实用的..."
category: 案例研究
tags: ['AI协作', '案例研究']
difficulty: 进阶
---
# 案例研究：构建 AI 驱动的任务优先级排序工具

在本案例中，我们将演示如何利用"全周期 AI 工作流"快速从 0 到 1 构建一个实用的小工具：**AI-Powered CLI Task Prioritizer**。这个工具能够帮助开发者将杂乱的任务列表转化为一个基于"价值-成本"矩阵的优先级清单。

## 项目背景

### 问题定义
每个开发者都面临任务过多的困境。当你有 20 个待办事项时，如何决定先做哪个？传统方法是凭直觉，但这往往导致高价值任务被低价值紧急任务挤占。

我尝试过多种方法：看板、GTD、Eisenhower 矩阵，但都缺少一个关键要素——**量化评估**。直觉告诉我们"这个任务很重要"，但很少有人能说清楚"为什么重要"以及"相对于其他任务有多重要"。

### 核心需求
构建一个 CLI 工具，能够：
1. 读取任务列表（从文件或标准输入）
2. 使用 LLM 分析每个任务的价值和成本
3. 基于 Value/Effort 比率排序
4. 输出格式化的优先级清单

### 技术约束
- 纯 Python 实现，无外部依赖
- 支持模拟模式（无需真实 LLM API）
- 单元测试覆盖核心逻辑
- 可作为独立脚本运行

## 1. 需求阶段 (Requirement Phase)：从模糊想法到 PRD

最初的想法很简单："我想让 AI 帮我给任务排优先级"。但如果直接写代码，很容易漏掉边界情况。于是，我首先利用 AI 将其转化为一份正式的 **PRD (产品需求文档)**。

**AI 协作过程：**
我向 AI 描述了核心痛点（任务太多，不知道先做哪个），并要求它定义一个基于 `Value vs Effort` 的打分模型。AI 迅速提出了一个量化的方案：
- **价值 (Value)**: 1-10 分
- **成本 (Effort)**: 1-10 分
- **优先级得分** = $\frac{Value}{Effort}$

通过这次对话，我明确了输入（文件/stdin）、输出（格式化表格）以及技术约束（Python, JSON 接口）。这避免了在开发过程中频繁修改需求。

**AI 协作 Prompt:**
```markdown
我想构建一个任务优先级排序 CLI 工具。

**核心痛点：**
- 任务太多，不知道先做哪个
- 缺乏量化评估标准
- 手动排序耗时且主观

**目标用户：**
个人开发者和小团队

**核心功能：**
1. 读取任务列表（文件或 stdin）
2. 使用 LLM 分析价值和成本
3. 基于 Value/Effort 排序
4. 输出格式化表格

**技术约束：**
- Python 3.11+
- 无外部依赖
- 支持模拟模式

请帮我输出一份 PRD，包括用户故事、功能列表、技术约束。
```

**AI 输出:** 完整的 PRD 文档，包含用户故事、功能优先级、技术选型建议。

## 2. 设计阶段 (Design Phase)：定义契约

在编码之前，我要求 AI 根据 PRD 生成一份 **设计文档**。这步的关键在于定义 **API 契约**。

**AI 协作 Prompt:**
```markdown
基于 PRD，请设计系统架构。

**技术约束：**
- Python 3.11+
- 无外部依赖
- 支持模拟模式

**请输出：**
1. 模块划分 (ASCII 架构图)
2. 核心接口定义
3. 数据流设计
4. 错误处理策略
```

**设计核心：**
- **分层架构**: `CLI Layer` → `Logic Layer` → `Infrastructure Layer`
- **LLM 契约**: 定义了严格的 JSON 输出格式：`[{"task": "...", "value": 8, "effort": 2}]`

这种"契约先行"的方法意味着我可以先编写测试用例，而不需要等待 LLM 接口真正可用。

**AI 输出:** 分层架构设计，包含：
- `Prioritizer`: 核心排序逻辑
- `LLMClient`: LLM 接口封装
- `main.py`: CLI 入口

## 3. 迭代编码阶段 (Iterative Coding Phase)：TDD 循环

我采用了 **TDD (测试驱动开发)** 的循环：`Prompt → Test → Implement → Verify`。

### 循环 1：核心排序逻辑

**Test First:**
```python
def test_prioritizer_sorts_by_value_effort_ratio():
    tasks = [
        {"task": "High value, low effort", "value": 9, "effort": 2},
        {"task": "Low value, high effort", "value": 2, "effort": 9},
    ]
    prioritizer = Prioritizer()
    result = prioritizer.prioritize(tasks)
    assert result[0]["task"] == "High value, low effort"
    assert result[0]["score"] == 4.5
```

**Implement:**
```python
class Prioritizer:
    def prioritize(self, tasks: list[dict]) -> list[dict]:
        for task in tasks:
            value = int(task.get("value", 0))
            effort = int(task.get("effort", 1))
            task["score"] = value / effort if effort > 0 else 0
        return sorted(tasks, key=lambda x: x["score"], reverse=True)
```

**Verify:** `pytest tests/test_prioritizer.py -v` → **Passed**

### 循环 2：LLM 客户端

**Implement:**
```python
class LLMClient:
    def __init__(self, provider="mock"):
        self.provider = provider

    def analyze_tasks(self, tasks: list[str]) -> list[dict]:
        if self.provider == "mock":
            return self._mock_response(tasks)
        # Real LLM implementation here
```

**Verify:** 通过 `main.py` 进行端到端测试 → **Passed**

## 4. 优化与精炼 (Refinement)：处理意外 Bug

在测试过程中，我遇到了一个典型的 AI 集成问题：**类型不一致**。

**Bug 场景：**
LLM 有时会返回字符串类型的数字 (例如 `"8"` 而不是 `8`)，导致 Python 在执行 `value / effort` 时抛出 `TypeError: unsupported operand type(s) for /: 'str' and 'str'`。

**修复过程：**
1. **诊断**: 运行工具 → 触发崩溃 → 查看 Traceback
2. **修复**: 在 `Prioritizer` 中增加显式的类型转换 `int(item.get("value", 0))`
3. **验证**: 重新运行 → **Fixed**

这个过程体现了 AI 开发中的一个重要原则：**永远不要信任 LLM 返回的原始类型，必须进行强制转换或 Schema 验证。**

**AI 协作 Prompt:**
```markdown
我的工具在运行时抛出 TypeError:
TypeError: unsupported operand type(s) for /: 'str' and 'str'

这是因为 LLM 返回了字符串类型的数字。请帮我：
1. 分析根本原因
2. 提供修复方案
3. 建议预防措施
```

**AI 输出:** 类型转换修复 + Schema 验证建议 + 预防性编码模式

## 5. 最终结果 (Final Result)

### 完成的代码结构
```text
ai-task-prioritizer/
├── PRD.md             # 需求定义
├── DESIGN.md          # 架构设计
├── main.py            # CLI 入口
├── prioritizer.py     # 排序逻辑 (Core)
├── llm_client.py      # LLM 接口封装
└── tests/
    └── test_prioritizer.py # 单元测试
```

### 效率提升分析

| 阶段 | 传统手动开发 (预估) | AI 辅助开发 (实际) | 提升 |
| :--- | :--- | :--- | :--- |
| 需求分析 & PRD | 2 小时 | 10 分钟 | 12x |
| 架构设计 & 契约 | 1 小时 | 5 分钟 | 12x |
| 编码 & TDD 循环 | 4 小时 | 30 分钟 | 8x |
| 调试 & 修复 | 1 小时 | 10 分钟 | 6x |
| **总计** | **8 小时** | **~1 小时** | **~8x** |

**反思：**
AI 最大的价值不在于"写代码"，而在于"压缩思考路径"。通过 PRD → Design → Test 的标准链路，我将一个可能需要一整天的开发任务压缩到了一小时内，且代码具有极高的可维护性。

**真实数据参考**：
- **Boldare**: 测试覆盖率提升 10 个百分点，冲刺速度提升 31%，AI 触及 75-85% 新代码
- **Coinbase**: 从想法到生产时间减少 90%（20 天 → 1.8 天），75% PR 由 Agent 创建
- **Payphone**: 常规任务快 20%，测试覆盖率从 26% 提升至 47%，PR 大小减少 47%

## 关键洞察

### 1. 契约先行
先定义接口，再实现细节。这使得 TDD 成为可能，因为测试可以在实现之前编写。

### 2. TDD 循环
测试驱动开发确保质量。每个功能都有对应的测试，回归测试覆盖率高。

### 3. 类型验证
永远不要信任 LLM 返回的原始类型。必须进行强制转换或 Schema 验证，这是 AI 集成的铁律。

### 4. 文档即代码
PRD 和设计文档成为代码的一部分，而不是束之高阁的文档。这保证了文档与代码的一致性。

### 5. 模拟模式
支持模拟模式使得开发和测试可以在没有真实 LLM API 的情况下进行，降低了开发门槛。

---

## 适用场景

- 个人开发者任务管理
- 小团队优先级排序
- 项目管理工具集成
- 自动化工作流触发

**典型项目特征:**
- 任务列表超过 10 项，手动排序效率低
- 需要量化评估任务价值和成本
- 希望减少主观判断，提高决策质量
- 需要可重复的优先级排序流程

---

**📂 导航**
- [[../INDEX.md|⬅️ 返回知识地图]]
- **相关案例**: [[case-studies/ai-context-sync-development|AI-Context-Sync 开发]]
- **相关文章**: [[../docs/efficiency/full-cycle-workflow|全周期工作流]] | [[../docs/learning/prompt-engineering|Prompt 工程]]
