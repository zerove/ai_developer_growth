# AI Context Sync

> 自动维护项目 `CONTEXT.md` 和 `ADR.md` 的 AI 上下文同步工具。

---

## 定位

验证 `docs/efficiency/full-cycle-workflow` 中的全周期工作流和 `learning/prompt-engineering` 中的 Prompt 工程方法论。

## 核心能力

| 功能 | 描述 |
|------|------|
| `dx sync` | 自动同步 CONTEXT.md（项目状态、决策、计划） |
| `dx guard` | ADR 守护：防止未记录的架构决策 |
| `dx audit` | 规范审计：检查代码是否符合项目规范 |
| `dx flow` | AI 原生开发流程：需求 → 设计 → 实现 → 审查 |
| `dx trace` | 决策追踪：从需求到代码的完整链路 |
| `dx evolve` | 规范演化：基于使用数据优化规范 |

## MCP Server 集成

可通过 MCP Server 方式集成到 OpenCode 等 AI IDE。

## 快速开始

```bash
pip install -e .

# 同步上下文
dx sync

# ADR 守护
dx guard --branch feature/xxx

# 规范审计
dx audit --fix
```

## 测试

```bash
python -m pytest tests/ -v
```

## 相关文档

- [[docs/efficiency/full-cycle-workflow|全周期工作流]]
- [[docs/learning/prompt-engineering|Prompt 工程]]
