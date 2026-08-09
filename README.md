# 🚀 AI Developer Growth

[![CI](https://img.shields.io/badge/CI-passing-brightgreen)](#)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Coverage](https://img.shields.io/badge/Coverage-84%25-brightgreen)](#)
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
| 缺少真实案例参考 | 📚 35+ 实践案例 |

---

## 📚 知识地图

### 🧠 认知升级
理解 AI 时代的游戏规则。

### 📚 学习方法
掌握 AI 时代的学习范式。

### ⚡ 工程效率
将认知转化为生产力。

---

## 📈 实践案例

真实的 AI 协作开发案例，验证效率提升:

| 案例 | 场景 | 效率提升 | 链接 |
|------|------|----------|------|
| 🔥 Cursor 大规模重构 | 12 万行代码架构迁移 | **3x** | [[case-studies/cursor-refactoring]] |
| 🧪 Copilot 测试生成 | 自动化测试补充 | **3.4x** | [[case-studies/copilot-test-generation]] |
| 🏗️ Claude 架构设计 | 系统设计与评审 | **3.3x** | [[case-studies/claude-architecture-design]] |
| 🤖 多 Agent 自动化 | 团队协作自动化 | **9.3x** | [[case-studies/multi-agent-automation]] |
| 🛠️ AI 任务优先级 | 从 0 到 1 CLI 工具 | **8x** | [[case-studies/ai-task-prioritizer]] |
| 🔄 AI-Context-Sync | 完整产品开发 | **12x** | [[case-studies/ai-context-sync-development]] |
| 🧬 AI-Native 主管道 | 全生命周期研发自动化 | **12x** | [[case-studies/jcode-ai-native-master-workflow-execution]] |
| 🏛️ 治理自审计 | 用自己的药医自己 | **-85 问题** | [[case-studies/governance-self-audit]] |

**现状**: 43 个真实案例，覆盖不同规模和场景。目标是 35+，已超额完成。

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

# 运行测试
pytest
```

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
python ai-dev-framework/core/jcode_init.py your-project --language python
```

---

## 🛠️ 代码示例

可运行的参考实现:

| 示例 | 功能 | 亮点 |
|------|------|------|
| [[examples/ai-context-sync\|ai-context-sync]] | 上下文同步 MCP Server | 多 LLM 支持 |
| [[examples/ai-navigation\|ai-navigation]] | AI 知识导航系统 | RAG + 个性化推荐 |
| [[examples/multi-agent-orch\|multi-agent-orch]] | 多 Agent 编排 | 4 角色协作 |
| [[examples/self-correction-loop\|self-correction-loop]] | 自我修正循环 | 验证→重试模式 |
| [[examples/prompt-optimizer\|prompt-optimizer]] | Prompt 优化器 | LLM 评分 |

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
| 📄 核心文档 | 253 篇 |
| 📚 实践案例 | 43 个 |
| 🛠️ 代码示例 | 10 个 |
| 📋 架构决策 | 10 条 |
| 🧪 测试用例 | 2513 个 |
| ✅ 测试覆盖率 | 85%+ |

---

## 🏗️ 项目结构

```
ai_developer_growth/
├── docs/                    # 253 篇方法论文档
│   ├── mindset/            # 认知升级
│   ├── learning/           # 学习方法
│   ├── efficiency/         # 工程效率
│   ├── tools/              # 工具选型
│   └── adr/                # 架构决策
├── case-studies/            # 43 个实践案例
├── examples/                # 10 个代码示例
├── ai-dev-framework/        # 通用治理框架
│   └── core/               # 可移植组件
├── tools/scripts/           # 自动化工具
│   ├── hooks/              # 模块化 Hook 系统
│   │   ├── basic_checks.py # lint/format/typecheck/test/security
│   │   ├── domain_checks.py# language-rules/quality-gate/governance
│   │   └── incremental.py  # diff/pre-commit 增量检查
│   ├── rules_engine/       # 规则引擎 (26 语言)
│   └── rule_catalog.py     # 规则包管理
├── agents/                  # Agent 定义
├── tests/                   # 2500+ 个测试
```

---

## 📜 治理标准

本项目包含一套**通用的** AI Agent 开发治理标准，可复制到任何项目:

- **GOVERNANCE.md** - 完整的治理标准
- **4 道质量门禁** - 确保代码质量
- **13 种语言规范** - Python, TypeScript, Rust, Go...
- **11 种框架规范** - React, Vue, FastAPI, Spring Boot...

详见 [[docs/agent-dev/quality-gates|质量门禁]]。

---

## 📄 License

MIT License - 详见 [[LICENSE]]

---

_AI 时代的竞争不是人与 AI 的竞争，而是掌握 AI 的人与不掌握 AI 的人的竞争。_

_Last Updated: 2026-07-23_
