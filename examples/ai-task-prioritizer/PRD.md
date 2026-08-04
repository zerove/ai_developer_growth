# PRD: AI 任务优先级排序工具 (AI Task Prioritizer)

## 1. 目标 (Goal)
创建一个命令行工具，利用 LLM 将用户提供的任务列表根据“价值 (Value)”和“成本 (Effort)”两个维度进行打分并排序，帮助用户快速识别“低挂的果实 (Low-hanging fruit)”（高价值、低成本任务）。

## 2. 核心功能 (Core Features)
- **输入**: 接收一个包含任务描述的列表（支持文本文件或标准输入）。
- **AI 分析**: 调用 LLM 为每个任务评估：
    - 价值 (Value): 1-10 分
    - 成本 (Effort): 1-10 分
- **优先级计算**: 使用公式 `Priority = Value / Effort` 或类似的逻辑进行排序。
- **输出**: 以表格形式输出排序后的任务列表，包括得分和建议的优先级类别（如：立即执行、计划执行、考虑放弃）。

## 3. 用户流程 (User Flow)
1. 用户运行命令: `prioritize tasks.txt`
2. 工具读取 `tasks.txt`。
3. 工具将任务列表发送给 LLM，要求其按特定 JSON 格式返回打分结果。
4. 工具解析 JSON，计算优先级并排序。
5. 工具在终端打印格式化后的结果。

## 4. 技术约束 (Constraints)
- 使用 Python 编写。
- 支持通过环境变量配置 LLM API Key。
- LLM 输出必须是严格的 JSON 格式以便解析。
