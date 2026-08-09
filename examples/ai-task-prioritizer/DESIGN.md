# Design: AI Task Prioritizer

## 1. 架构图 (Architecture)
`CLI` -> `Prioritizer` -> `LLM Client` -> `LLM API`

## 2. 模块职责 (Module Responsibilities)
- **main.py (CLI Layer)**:
    - 处理命令行参数 (`argparse`)。
    - 读取输入文件。
    - 调用 `Prioritizer` 并打印最终结果。
- **prioritizer.py (Logic Layer)**:
    - 构建发送给 LLM 的 Prompt。
    - 调用 `LLMClient` 获取原始打分数据。
    - 计算优先级分数 (`Value / Effort`)。
    - 对任务进行排序。
- **llm_client.py (Infrastructure Layer)**:
    - 封装 API 调用 (如 OpenAI 或 Claude)。
    - 处理 API 错误和重试。
    - 确保输出被解析为 JSON。

## 3. API 契约 (API Contracts)
### LLM Prompt 结构
- **输入**: 任务列表 (string list)。
- **输出格式**:
  ```json
  [
    { "task": "任务名称", "value": 8, "effort": 3 },
    ...
  ]
  ```

### 内部函数签名
- `LLMClient.get_scores(tasks: List[str]) -> List[Dict]`
- `Prioritizer.prioritize(tasks: List[str]) -> List[PrioritizedTask]`
- `PrioritizedTask` 结构: `(task, value, effort, score, category)`
