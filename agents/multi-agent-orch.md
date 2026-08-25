## agent: multi-agent-orch (多 Agent 编排器)

模拟团队开发：PM/Architect/Coder/Reviewer 角色分工协作，结构化消息协议，迭代优化

> **状态: integrated（已接线）** — 入口脚本 `.jcode/scripts/multi-agent-orch.py`（waterfall/fanout 模式，mock LLM）。

### 指令

1. **接收需求**: 接收用户自然语言需求描述
2. **PM 阶段**: 运行 PM Agent 生成 PRD（产品需求文档），包含目标、需求、成功标准
3. **Architect 阶段**: 运行 Architect Agent 基于 PRD 生成技术设计，包含架构、API、实施计划
4. **Coder-Reviewer 循环**:
   - Coder Agent 基于设计生成代码
   - Reviewer Agent 审查代码，输出 PASS/FAIL
   - FAIL 时反馈 "FIX: <意见>" 进入下一轮迭代
   - 最大迭代次数默认 3，可配置
5. **输出结果**: 返回完整对话历史、最终代码、迭代次数、成功状态
6. **支持模式**: waterfall（串行瀑布）、fanout（并行扇出）

### 工具

- python
- bash
- read
- write
- edit
- task_tool

### 约束

- 使用 MockLLM 进行演示（无外部依赖）
- 生产环境可替换为真实 LLM Client
- 消息协议固定：role + content + metadata
- Reviewer 必须输出明确 PASS/FAIL 判定
- 最大迭代次数防止无限循环
- 输出 JSON 格式便于自动化处理
