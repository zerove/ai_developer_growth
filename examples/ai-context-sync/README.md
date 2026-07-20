# AI-Context-Sync

> **定位**: 参考实现 | 验证 ai_developer_growth 知识体系的实践工具

---

## 这是什么？

AI-Context-Sync 是一个自动维护项目上下文的 AI 工具。它不是核心产品，而是**知识验证工具**——用于检验 [[docs/efficiency/full-cycle-workflow|全周期工作流]] 和 [[learning/prompt-engineering|Prompt 工程]] 在真实场景中的效果。

**核心价值**:
- 验证 AI 协作开发方法论
- 展示 TDD + AI 的实践效果
- 作为 [[case-studies/ai-context-sync-development|案例研究]] 的代码基础

---

## 功能

- **上下下文同步**: 自动维护 `CONTEXT.md`
- **ADR 生成**: 架构决策自动记录
- **规范审计**: 代码是否符合项目规范
- **多 LLM 支持**: OpenAI、Claude、Ollama、系统自动检测

---

## 快速开始

### 1. 安装依赖
```bash
pip install -r requirements.txt
export AI_SYNC_KEY="your-api-key"
```

### 2. 初始化项目
```bash
python3 -m src.cli init
```

### 3. 集成到 opencode (可选)
如需将 AI-Context-Sync 作为 MCP 服务器集成到 opencode，请参考 [MCP 配置指南](MCP_SETUP.md)。

**快速配置：**
在项目根目录创建 `opencode.json`：
```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "ai-context-sync": {
      "command": "python",
      "args": ["-m", "src.mcp_server"],
      "cwd": "$PWD",
      "enabled": true
    }
  }
}
```

---

## 开发流程

本工具的开发过程本身就是 [[case-studies/ai-context-sync-development|案例研究]]：

1. **TDD 驱动**: 先写测试，再写实现
2. **Prompt 工程**: 使用结构化 Prompt 生成代码
3. **渐进式开发**: 每次只做一个小功能

---

## 相关文档

- [[case-studies/ai-context-sync-development|开发案例]] - 完整开发流程
- [[docs/efficiency/full-cycle-workflow|全周期工作流]] - 方法论
- [[learning/prompt-engineering|Prompt 工程]] - 技巧

---

*这是知识验证工具，非核心产品。核心价值在知识文档中。*
