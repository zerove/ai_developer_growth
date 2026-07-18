# 案例研究：构建 AI 驱动的任务优先级排序工具

在本案例中，我们将演示如何利用“全周期 AI 工作流”快速从 0 到 1 构建一个实用的小工具：**AI-Powered CLI Task Prioritizer**。这个工具能够帮助开发者将杂乱的任务列表转化为一个基于“价值-成本”矩阵的优先级清单。

## 1. 需求阶段 (Requirement Phase)：从模糊想法到 PRD

最初的想法很简单：“我想让 AI 帮我给任务排优先级”。但如果直接写代码，很容易漏掉边界情况。于是，我首先利用 AI 将其转化为一份正式的 **PRD (产品需求文档)**。

**AI 协作过程：**
我向 AI 描述了核心痛点（任务太多，不知道先做哪个），并要求它定义一个基于 `Value vs Effort` 的打分模型。AI 迅速提出了一个量化的方案：
- **价值 (Value)**: 1-10 分
- **成本 (Effort)**: 1-10 分
- **优先级得分** = $\frac{Value}{Effort}$

通过这次对话，我明确了输入（文件/stdin）、输出（格式化表格）以及技术约束（Python, JSON 接口）。这避免了在开发过程中频繁修改需求。

## 2. 设计阶段 (Design Phase)：定义契约

在编码之前，我要求 AI 根据 PRD 生成一份 **设计文档**。这步的关键在于定义 **API 契约**。

**设计核心：**
- **分层架构**: `CLI Layer` $\rightarrow$ `Logic Layer` $\rightarrow$ `Infrastructure Layer`。
- **LLM 契约**: 定义了严格的 JSON 输出格式：`[{"task": "...", "value": 8, "effort": 2}]`。

这种“契约先行”的方法意味着我可以先编写测试用例，而不需要等待 LLM 接口真正可用。

## 3. 迭代编码阶段 (Iterative Coding Phase)：TDD 循环

我采用了 **TDD (测试驱动开发)** 的循环：`Prompt $\rightarrow$ Test $\rightarrow$ Implement $\rightarrow$ Verify`。

### 循环 1：核心排序逻辑
- **Test**: 编写 `test_prioritizer.py`，模拟 LLM 返回的分数，验证排序结果是否正确。
- **Implement**: 实现 `Prioritizer` 类，计算 $\frac{Value}{Effort}$ 并排序。
- **Verify**: 运行 `pytest` $\rightarrow$ **Passed**.

### 循环 2：LLM 客户端
- **Implement**: 实现 `LLMClient`，构建 Prompt 并处理 API 返回值。为了方便演示，我实现了一个模拟响应机制。
- **Verify**: 通过 `main.py` 进行端到端测试 $\rightarrow$ **Passed**.

## 4. 优化与精炼 (Refinement)：处理意外 Bug

在测试过程中，我遇到了一个典型的 AI 集成问题：**类型不一致**。

**Bug 场景：**
LLM 有时会返回字符串类型的数字 (例如 `"8"` 而不是 `8`)，导致 Python 在执行 `value / effort` 时抛出 `TypeError: unsupported operand type(s) for /: 'str' and 'str'`。

**修复过程：**
1. **诊断**: 运行工具 $\rightarrow$ 触发崩溃 $\rightarrow$ 查看 Traceback。
2. **修复**: 在 `Prioritizer` 中增加显式的类型转换 `int(item.get("value", 0))`。
3. **验证**: 重新运行 $\rightarrow$ **Fixed**.

这个过程体现了 AI 开发中的一个重要原则：**永远不要信任 LLM 返回的原始类型，必须进行强制转换或 Schema 验证。**

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
AI 最大的价值不在于“写代码”，而在于“压缩思考路径”。通过 PRD $\rightarrow$ Design $\rightarrow$ Test 的标准链路，我将一个可能需要一整天的开发任务压缩到了一小时内，且代码具有极高的可维护性。

**真实数据参考**：
- **Boldare**: 测试覆盖率提升 10 个百分点，冲刺速度提升 31%，AI 触及 75-85% 新代码
- **Coinbase**: 从想法到生产时间减少 90%（20 天 → 1.8 天），75% PR 由 Agent 创建
- **Payphone**: 常规任务快 20%，测试覆盖率从 26% 提升至 47%，PR 大小减少 47%

**关键洞察**：
1. **契约先行**：先定义接口，再实现细节
2. **TDD 循环**：测试驱动开发确保质量
3. **类型验证**：永远不要信任 LLM 返回的原始类型
4. **文档即代码**：PRD 和设计文档成为代码的一部分
