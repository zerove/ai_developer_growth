# 🚀 AI Developer Growth

[![CI](https://img.shields.io/badge/CI-passing-brightgreen)](#)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Coverage](https://img.shields.io/badge/Coverage-86%25-brightgreen)](#)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)
[![Stars](https://img.shields.io/github/stars/zerove/ai_developer_growth)](https://github.com/zerove/ai_developer_growth/stargazers)

> **AI 时代的开发者成长知识库**
>
> 当 AI 能写出 80% 的代码时，你的价值在于**定义问题、系统设计、快速迭代**。

---

## 💡 为什么需要这个项目？

| 痛点 | 解决方案 |
|------|----------|
| AI 工具太多，不知如何选择 | 📊 工具矩阵对比 |
| 不知道如何与 AI 协作 | 🔄 全周期工作流 |
| 担心被 AI 取代 | 🧠 认知升级方法论 |
| 缺少真实案例参考 | 📚 48 个实践案例 |

---

## 📚 知识地图

完整索引见 [docs/MOC.md](docs/MOC.md)（409 篇文档）。

### 🧠 认知升级
理解 AI 时代的游戏规则。

- [[docs/mindset/capability-model|能力模型]] · [[docs/mindset/ai-to-market-checklist|AI 到市场检查清单]] · [[docs/mindset/career-transformation|职业转型]]

### 📚 学习方法
掌握 AI 时代的学习范式。

- [[docs/learning/ai-learning-method|AI 学习法]] · [[docs/learning/ai-learning-path|学习路径]] · [[docs/learning/capability-levels|能力分级]]

### ⚡ 工程效率
将认知转化为生产力。

- [[docs/efficiency/README|效率层总览]] · [[docs/efficiency/full-cycle-workflow|全周期工作流]] · [[docs/efficiency/ai-architecture-design|AI 架构设计]]

### 🛠️ 工具选型
工具矩阵与选型依据。

- [[docs/tools/ai-tool-matrix|AI 工具矩阵]]

---

## 📈 实践案例

真实的 AI 协作开发案例，验证效率提升:

| 案例 | 场景 | 效率提升 | 链接 |
|------|------|----------|------|
| 🔥 Cursor 大规模重构 | 12 万行代码架构迁移 | **3x** | [[docs/case-studies/cursor-refactoring]] |
| 🧪 Copilot 测试生成 | 自动化测试补充 | **3.4x** | [[docs/case-studies/copilot-test-generation]] |
| 🏗️ Claude 架构设计 | 系统设计与评审 | **3.3x** | [[docs/case-studies/claude-architecture-design]] |
| 🤖 多 Agent 自动化 | 团队协作自动化 | **9.3x** | [[docs/case-studies/multi-agent-automation]] |
| 🛠️ AI 任务优先级 | 从 0 到 1 CLI 工具 | **8x** | [[docs/case-studies/ai-task-prioritizer]] |
| 🔄 AI-Context-Sync | 完整产品开发 | **12x** | [[docs/case-studies/ai-context-sync-development]] |
| 🧬 AI-Native 主管道 | 全生命周期研发自动化 | **12x** | [[docs/case-studies/jcode-ai-native-master-workflow-execution]] |
| 🏛️ 治理自审计 | 用自己的药医自己 | **-85 问题** | [[docs/case-studies/governance-self-audit]] |

**现状**: 48 个真实案例（另含 1 个社区贡献模板），覆盖不同规模和场景。目标是 35+，已超额完成。

---

## 🚀 快速开始

### 1. 阅读核心方法论

```
产品思维 → AI 学习法 → Prompt 工程 → 全周期工作流
```

### 2. 应用到你的项目

```bash
# 克隆项目
git clone https://github.com/zerove/ai_developer_growth.git
cd ai_developer_growth

# 安装依赖
pip install -r requirements-dev.txt

# 安装 pre-push 门禁（强烈建议）
make setup-git

# 运行测试
pytest
```

> **⚠️ 关于 pre-push 门禁**
>
> `.git/` 不受版本控制，因此门禁**不会**随克隆自动出现。`make setup-git` 会把
> 受跟踪的 `.jcode/hooks/pre-push` 安装到 `.git/hooks/pre-push`，之后每次推送
> 都会执行 lint / typecheck / test / quality-gate / baseline 五项检查。
>
> 这是本项目最有价值的机制——它曾在本次维护中拦下 279 个仅靠测试与 lint
> 无法发现的类型错误。详见 [ADR-057](docs/adr/ADR-057-ci-heartbeat-outside-ci.md)。

### 3. 集成到你的工具链

#### opencode (MCP)

```bash
# 配置 opencode
cat > opencode.json << 'EOF'
{
  "mcp": {
    "ai-context-sync": {
      "command": "python",
      "args": ["-m", "src.mcp_server"],
      "cwd": "./examples/ai-context-sync"
    }
  }
}
EOF
```

#### jcode (AI Agent)

```bash
# 初始化项目
python ai-dev-framework/src/ai_dev_framework/jcode_init.py your-project --language python
```

---

## 🛠️ 代码示例

可运行的参考实现:

| 示例 | 功能 | 亮点 |
|------|------|------|
| [[examples/ai-context-sync/README\|ai-context-sync]] | 上下文同步 MCP Server | 多 LLM 支持 |
| [[examples/ai-navigation/README\|ai-navigation]] | AI 知识导航系统 | RAG + 个性化推荐 |
| [[examples/multi-agent-orch/README\|multi-agent-orch]] | 多 Agent 编排 | 4 角色协作 |
| [[examples/self-correction-loop/README\|self-correction-loop]] | 自我修正循环 | 验证→重试模式 |
| [[examples/prompt-optimizer/README\|prompt-optimizer]] | Prompt 优化器 | LLM 评分 |

---

## 🤝 参与贡献

我们欢迎任何形式的贡献:

| 类型 | 描述 | 难度 |
|------|------|------|
| 💡 案例分享 | 你用 AI 完成了什么？ | ⭐ |
| 🔧 工具推荐 | 发现了好用的 AI 工具？ | ⭐ |
| 📝 方法论改进 | 对现有内容有修正？ | ⭐⭐ |
| 🐛 问题反馈 | 发现了过时或错误？ | ⭐ |
| 🚀 新功能 | 添加新的示例或文档？ | ⭐⭐⭐ |

详见 [[CONTRIBUTING|贡献指南]]。

---

## 📊 项目统计

| 指标 | 数量 |
|------|------|
| 📄 核心文档 | 412 篇 |
| 📚 实践案例 | 48 个 |
| 🛠️ 代码示例 | 10 个 |
| 📋 架构决策 | 73 条 |
| 🧪 测试用例 | 5935 个（`pytest --collect-only`） |
| ✅ 测试覆盖率 | 87% |

### 🔌 自检：门禁是否还活着

门禁自己可能悄悄失效。本项目提供三个自检入口：

```bash
make doctor        # 本地门禁环境（工具链/插件/基线是否就绪）
make ci-heartbeat  # 远端 CI 是否真的跑过 job
make ci-alert      # 同上，额外以去重 Issue 方式开/更新告警、恢复时自动关闭
make self-check    # doctor + ci-heartbeat
```

`ci-heartbeat` / `ci-alert` 需要 `GITHUB_TOKEN`（`repo` 权限）：

```bash
GITHUB_TOKEN=<your_token> make ci-alert
```

`ci-alert` 的告警 Issue 用固定标题去重，同一时间只存在一条：失效时新建或更新，
**恢复后自动关闭**。因此该 Issue 的存续即代表"当前失效"，无需人工清理。

可接入系统 cron 做被动告警（注意：不能放进 CI，理由见下）：

```cron
0 9 * * * cd /path/to/repo && GITHUB_TOKEN=xxx make ci-alert
```

**为什么 `ci-heartbeat` 必须在本地跑，不能注册成 scheduled 工作流？**

私有仓库的 Actions 消耗账户分钟配额。配额耗尽时 run 被立即拒绝：不分配 runner、
不产生任何 job。本项目的 CI 曾在 2026-09-05 至 09-29 期间持续处于该状态达 23 天
而无人察觉。跑在 CI 内的任何检测器都会与它要监测的门禁一起死亡，无法自检。
详见 [ADR-057](docs/adr/ADR-057-ci-heartbeat-outside-ci.md)。

---

## 🏗️ 项目结构

```
ai_developer_growth/
├── docs/                    # 409 篇文档
│   ├── mindset/            # 认知升级
│   ├── learning/           # 学习方法
│   ├── efficiency/         # 工程效率
│   ├── tools/              # 工具选型
│   └── adr/                # 架构决策
│   └── case-studies/        # 48 个实践案例（位于 docs/ 下以供 MkDocs 构建）
├── examples/                # 10 个代码示例
├── ai-dev-framework/        # 通用治理框架
│   └── standards/          # 通用治理标准
├── tools/scripts/           # 自动化工具
│   ├── hooks/              # 模块化 Hook 系统
│   │   ├── basic_checks.py # lint/format/typecheck/test/security
│   │   ├── domain_checks.py# language-rules/quality-gate/governance
│   │   └── incremental_checks.py # diff/pre-commit 增量检查
│   ├── rules_engine/       # 规则引擎 (26 语言)
│   └── rule_catalog.py     # 规则包管理
├── agents/                  # Agent 定义
├── tests/                   # 单元/契约测试
```

---

## 📜 治理标准

本项目包含一套**通用的** AI Agent 开发治理标准，可复制到任何项目:

- **GOVERNANCE.md** - 完整的治理标准
- **4 道质量门禁** - 确保代码质量
- **多语言规范** - 规则引擎当前内置 25 种语言 (Python, TypeScript, Rust, Go...)
- **9 种框架规范** - React, Vue, FastAPI, Spring Boot...

详见 [[docs/agent-dev/quality-gates|质量门禁]]。

---

## 📄 License

MIT License - 详见 [[LICENSE]]

---

_AI 时代的竞争不是人与 AI 的竞争，而是掌握 AI 的人与不掌握 AI 的人的竞争。_

_Last Updated: 2026-07-23_
