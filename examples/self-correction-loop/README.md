# 自我修正循环 (Self-Correction Loop) 原型

这是一个演示 AI 如何自动检测、分析并修复代码错误的简单原型。

## 工作流程

该原型实现了以下自动化闭环：
1. **运行测试 (Run Tests)**: 使用 Python `unittest` 模块执行测试套件。
2. **捕获错误 (Capture Error)**: 如果测试失败，捕获标准输出和错误流中的堆栈追踪。
3. **AI 修复 (AI Fix)**: 将故障代码和错误信息发送给 LLM（本原型支持 OpenAI API 或 演示模式下的 Mock AI）。
4. **应用修复 (Apply Fix)**: 将 AI 生成的修复代码自动写回源代码文件。
5. **验证 (Verify)**: 重新运行测试。如果仍然失败，则重复上述步骤，直到通过或达到最大重试次数。

## 快速开始

### 目录结构
- `src/`: 包含需要被修复的源代码。
- `tests/`: 包含验证代码正确性的测试用例。
- `self_correct.py`: 核心编排脚本。

### 运行步骤

1. **进入目录**:
   ```bash
   cd ai-developer-growth/examples/self-correction-loop/
   ```

2. **运行原型 (演示模式)**:
   默认情况下，如果没有配置 API Key，脚本将使用 Mock AI 来演示修复过程。
   ```bash
   python3 self_correct.py
   ```

3. **运行原型 (真实 AI 模式)**:
   如果你想使用真实的 GPT-4 进行修复，请安装 `openai` 库并配置环境变量：
   ```bash
   pip install openai
   export OPENAI_API_KEY='your-api-key-here'
   python3 self_correct.py
   ```

## 查看结果
运行结束后，你可以查看 `LOG.md` 以了解具体的自我修正过程。
