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

## 1 分钟 Demo 模式

```bash
# 快速体验：自动检测项目并生成 CONTEXT.md
dx demo

# Demo 模式会：
# 1. 检测项目语言和框架
# 2. 分析 git 历史生成最近变更
# 3. 自动创建 CONTEXT.md 和 ADR.md
# 4. 显示同步结果摘要
```

## 配置

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `CONTEXT_FILE` | `CONTEXT.md` | 上下文文件路径 |
| `ADR_DIR` | `docs/adr/` | ADR 存放目录 |
| `LLM_PROVIDER` | `auto` | LLM 提供商 (openai/claude/gemini/ollama/auto) |
| `IGNORE_DIRS` | `.git,node_modules` | 忽略的目录 |

## 边缘情况

- **大型仓库**: 使用 `.dxignore` 排除不需要同步的目录
- **多分支**: 使用 `dx sync --branch <name>` 指定分支
- **离线模式**: 设置 `LLM_PROVIDER=none` 跳过 AI 生成
- **CI/CD 集成**: 在 `.github/workflows/` 中添加 `dx sync --check` 验证上下文是否过期
- **冲突解决**: CONTEXT.md 冲突时使用 `dx sync --force` 覆盖

## 测试

```bash
python -m pytest tests/ -v
```

## 相关文档

- [[docs/efficiency/full-cycle-workflow|全周期工作流]]
- [[docs/learning/prompt-engineering|Prompt 工程]]
