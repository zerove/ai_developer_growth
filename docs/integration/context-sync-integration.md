---
title: 上下文同步集成
description: 如何使用 ai-context-sync 自动维护项目上下文
category: 集成
tags: ['AI', 'context', 'sync']
difficulty: 高级
reading_time: 8 分钟
updated: 2026-07-21
---

# 上下文同步集成

> 自动维护 CONTEXT.md 和 ADR.md 的 AI 上下文同步工具。

---

## 核心能力

| 命令 | 功能 |
|------|------|
| `dx sync` | 自动同步 CONTEXT.md |
| `dx guard` | ADR 守护，防止未记录的架构决策 |
| `dx audit` | 规范审计，检查代码合规性 |
| `dx flow` | AI 原生开发流程 |
| `dx trace` | 决策追踪 |
| `dx evolve` | 规范演化 |

## 快速开始

```bash
cd examples/ai-context-sync
pip install -e .

# 同步上下文
dx sync

# ADR 守护
dx guard --branch feature/xxx

# 规范审计
dx audit --fix
```

## MCP Server 集成

可通过 MCP Server 方式集成到 AI IDE：

```json
{
  "mcpServers": {
    "ai-context-sync": {
      "command": "python",
      "args": ["-m", "src.mcp_server"]
    }
  }
}
```

## 与知识库集成

- 自动从 Git 历史提取决策
- 生成 ADR.md 架构决策记录
- 同步项目状态到 CONTEXT.md

## 相关资源

- [[examples/ai-context-sync|示例代码]]
- [[efficiency/full-cycle-workflow|全周期工作流]]

---

*Last Updated: 2026-07-21*
