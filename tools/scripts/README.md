# AI 开发者自动化工具集

本目录包含用于减少 AI 驱动开发行政开销的自动化脚本。

## 工具列表

### 1. AI 上下文管理器 (`ai_context_manager.py`)
该脚本使用 LLM 自动更新项目的 `CONTEXT.md` 文件，确保项目进度实时同步。

**使用方法：**
```bash
# 方式 1：直接传递变更信息
python ai_context_manager.py "完成了 ADR 生成器的实现并添加了文档"

# 方式 2：交互式输入
python ai_context_manager.py
```

**环境变量：**
- `OPENAI_API_KEY`: 必需。您的 OpenAI API 密钥。
- `OPENAI_API_BASE`: 可选。API 基础路径 (默认: `https://api.openai.com/v1`)。

---

### 2. ADR 生成器 (`adr_generator.py`)
该脚本引导用户通过一系列提示生成标准化的架构决策记录 (Architecture Decision Record) 文件。

**使用方法：**
```bash
python adr_generator.py
```
脚本将提示您输入决策标题、背景、替代方案和最终结论，并在 `docs/adr/` 目录下生成 `.md` 文件。

## 安装依赖
```bash
pip install openai
```
