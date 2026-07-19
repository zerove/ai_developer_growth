# 🚀 AI-Native 研发操作系统：AI-Context-Sync 使用指南

欢迎使用 **AI-Context-Sync**。这不是一个简单的同步工具，而是一套旨在将“架构决策”、“研发规范”与“实时执行”深度绑定的 **AI-Native 研发操作系统**。

本系统旨在消除 AI 开发中的“上下文丢失”和“质量幻觉”，通过将知识资产化（Assets）和流程自动化（Automation），让开发者能够以极高精度驱动 LLM 完成复杂功能的构建。

---

## 📖 核心概念：三大知识资产

在开始使用工具前，请理解本系统维护的三大核心资产，它们是 AI 能够精准工作的“燃料”：

1.  **`CONTEXT.md` (项目记忆)**：记录项目的全局愿景、核心逻辑和当前进度。支持**分层结构**（根目录 $\rightarrow$ 模块 $\rightarrow$ 组件），确保 AI 在处理局部代码时拥有精准的局部认知。
2.  **`ADR.md` (决策图谱)**：记录所有关键架构决策（Architecture Decision Records）。通过 `Depends On` 和 `Supersedes` 建立决策之间的因果关系，防止架构漂移。
3.  **`docs/specs/` (语言规范)**：定义项目在该语言下的编码标准（如：Python 类型提示要求、Rust 内存管理约定）。这是 AI 审计代码的“法律依据”。

---

## 🛠 快速上手

### 1. 安装与环境准备
确保您已安装 Python 3.10+ 及相关依赖：
```bash
pip install typer unidiff watchdog
export AI_SYNC_KEY="您的-LLM-API-KEY"
```

### 2. 初始化配置
在项目根目录下运行，生成默认的 `.ai-sync.json` 配置文件：
```bash
python3 -m src.cli init
```

### 3. 集成到 opencode (可选)
如需将 AI-Context-Sync 作为 MCP 服务器集成到 opencode，请参考 [MCP 配置指南](../MCP_SETUP.md)。

**快速配置：**
在项目根目录创建 `opencode.json`：
```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "ai-context-sync": {
      "command": "python",
      "args": ["-m", "src.mcp_server"],
      "cwd": "/home/zeron/dev/ai_developer_growth/examples/ai-context-sync",
      "enabled": true
    }
  }
}
```

### 3. 运行首次同步
将最新的 Git 提交同步到项目上下文中：
```bash
python3 -m src.cli sync
```

---

## ⌨️ 指令详解

### 🔄 同步与守护 (Sync & Guard)
| 命令 | 说明 | 核心用途 |
| :--- | :--- | :--- |
| `sync` | 同步上下文 | 根据最新 commit 更新 `CONTEXT.md` 和生成 `ADR` |
| `guard` | 架构检查 | 检查当前变更是否违反了已记录的架构决策 (ADR) |
| `watch` | 实时守护 | 启动后台进程，保存文件时立即在 `docs/ai-audit-live.md` 更新审计结果 |

### ⚖️ 规范审计与演进 (Audit & Evolution)
| 命令 | 说明 | 核心用途 |
| :--- | :--- | :--- |
| `audit` | 规范审计 | 检查代码是否符合 `docs/specs/`。使用 `--strict` 可拦截非法提交 |
| `override` | 标记覆盖 | 将某个违规项标记为“本项目认可”，避免重复报警 |
| `evolve` | 规范演进 | 分析覆盖历史，自动提案更新过时的规范 |
| `apply-fix` | 一键修复 | 将 `dx watch` 建议的修复方案自动应用到源代码 |

### 🗺️ 决策追踪 (Trace & Map)
| 命令 | 说明 | 核心用途 |
| :--- | :--- | :--- |
| `trace <ID>` | 因果回溯 | 追踪某个决策（如 ADR-005）是由哪些前置决策导致的 |
| `map` | 生成图谱 | 自动生成 `docs/architecture_map.md` (Mermaid 流程图) |

### 🚀 自动化流水线 (The la-Phase 6 Flow)
`dx flow "任务描述"` 是本系统的最高级能力，它将上述所有能力串联为一个闭环：
**$\text{感知上下文} \rightarrow \text{分解子任务} \rightarrow \text{并行编码} \rightarrow \text{真实 TDD 验证} \rightarrow \text{全局规范审计} \rightarrow \text{资产同步}$**

---

## 🌟 推荐的 AI-Native 工作流

### 1. 开启“上帝视角” (实时开发模式)
- **终端 1**：运行 `dx watch`。
- **IDE 分屏**：右侧打开 `docs/ai-audit-live.md`。
- **操作**：编写代码 $\rightarrow$ 保存 $\rightarrow$ 查看右侧违规项 $\rightarrow$ 运行 `dx apply-fix` $\rightarrow$ 代码自动修正。

### 2. 实施复杂功能 (自动化交付模式)
- **指令**：运行 `dx flow "实现用户权限管理系统"`。
- **交互**：
    1. 审查 AI 生成의 **Technical Design** $\rightarrow$ 输入 `y` 确认。
    2. AI 自动拆分任务 $\rightarrow$ **并行实现** $\rightarrow$ **运行真实测试**。
    3. AI 自动执行 **Spec Audit** $\rightarrow$ 修复所有违规。
    4. 自动更新 `CONTEXT.md` $\rightarrow$ 交付成品。

### 3. 架构回顾 (知识管理模式)
- **操作**：运行 `dx map`。
- **价值**：在 `architecture_map.md` 中直观查看项目决策의 演进路径，确保新功能不破坏原有的架构初衷。

---

## ⚠️ 故障排除

- **ModuleNotFoundError**: 请确保环境变量 `PYTHONPATH` 包含项目根目录。
- **API Key 缺失**: 请检查 `AI_SYNC_KEY` 环境变量是否已正确设置。
- **审计误报**: 如果 AI 报告了错误的违规，请使用 `dx override <rule_id>` 标记，并运行 `dx evolve` 让 AI 学习您的偏好。

---

## 🛡️ 异常处理

项目采用分层异常体系，所有异常继承自 `AISyncError`：

| 异常类 | 触发场景 | 处理建议 |
|--------|----------|----------|
| `ConfigError` | 配置文件缺失或格式错误 | 运行 `dx init` 重新初始化 |
| `LLMError` | API 调用失败或超时 | 检查 `AI_SYNC_KEY` 和网络连接 |
| `GitError` | Git 操作失败 | 确保在 Git 仓库中运行 |
| `AuditError` | 审计流程异常 | 检查 `docs/specs/` 目录是否存在 |
| `WorkflowError` | 并行任务执行失败 | 查看具体任务的错误日志 |

```python
from src.exceptions import AISyncError, ConfigError

try:
    from src.core import AIContextSync
    sync = AIContextSync()
    sync.sync_context()
except ConfigError as e:
    print(f"配置错误: {e}")
except AISyncError as e:
    print(f"AI同步错误: {e}")
```

---

## 🧪 测试

运行项目测试套件：

```bash
# 运行全部测试
pytest tests/ -v

# 运行特定模块测试
pytest tests/test_auditor.py -v

# 类型检查
python -m mypy --package src
```
