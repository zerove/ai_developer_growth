# AI Developer Growth: 知识库

> **定位**: 开源知识库 | **目标**: 帮助开发者在 AI 时代实现指数级成长

## 核心问题

当 AI 能写出 80% 的代码时，开发者的价值在哪里？

**答案**: 定义问题、系统设计、快速迭代的能力。

本知识库不教你怎么写代码，而是教你**如何与 AI 协作**，成为更高效的开发者。

---

## 知识地图

### 🧠 认知升级
理解 AI 时代的游戏规则。

- [[docs/mindset/product-thinking|产品思维]] - 从"如何实现"到"构建什么"
- [[docs/mindset/solo-founder-loop|独立开发闭环]] - 一人公司的运作模式
- [[docs/mindset/ai-to-market-checklist|AI-to-Market 清单]] - 从代码到产品的路径

### 📚 学习方法
掌握 AI 时代的学习范式。

- [[docs/learning/ai-learning-method|AI 驱动学习法]] - 用 LLM 快速攻克新领域
- [[docs/learning/knowledge-internalization|知识内化]] - 避免 AI 依赖，构建底层能力
- [[docs/learning/prompt-engineering|Prompt 工程]] - 结构化提示词技巧

### ⚡ 工程效率
将认知转化为生产力。

- [[docs/efficiency/full-cycle-workflow|全周期工作流]] - 从需求到部署的 AI 协作流程
- [[docs/efficiency/automated-bug-fixing|自动化 Bug 修复]] - 感知→推理→行动→验证

### 🛠️ 工具选型
选择正确的工具组合。

- [[docs/tools/ai-tool-matrix|AI 工具矩阵]] - 模型、IDE、Agent 的对比与选型
- [[docs/tools/ide-best-practices|IDE 最佳实践]] - Zed/Cursor 配置与使用

---

## 实践案例

理论需要实践验证。以下是真实的 AI 协作开发案例：

| 案例 | 场景 | 效率提升 | 链接 |
|------|------|----------|------|
| AI 任务优先级工具 | 从 0 到 1 构建 CLI 工具 | 8x | [[case-studies/ai-task-prioritizer]] |
| AI-Context-Sync 开发 | 完整产品开发流程 | 12x | [[case-studies/ai-context-sync-development]] |
| 自我修正循环 | AI 代码质量保证 | 3x | [[examples/self-correction-loop]] |
| 多 Agent 协作 | 模拟团队开发 | 5x | [[examples/multi-agent-orch]] |

**目标**: 收集 10+ 真实案例，覆盖不同规模和场景。

---

## 快速开始

1. **阅读核心方法论** → 从 [[docs/mindset/product-thinking|产品思维]] 开始
2. **学习 AI 协作技巧** → [[docs/learning/ai-learning-method|AI 学习法]] + [[docs/learning/prompt-engineering|Prompt 工程]]
3. **查看实践案例** → [[case-studies/ai-task-prioritizer|案例库]]
4. **应用到你的项目** → [[docs/efficiency/full-cycle-workflow|全周期工作流]]

### 集成到 opencode (MCP)

AI-Context-Sync 提供 MCP 服务器，可直接集成到 opencode：

```bash
# 1. 安装依赖
cd examples/ai-context-sync
pip install -r requirements.txt

# 2. 配置 opencode (在项目根目录创建 opencode.json)
cat > opencode.json << 'EOF'
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
EOF
```

详细配置请参考 [[examples/ai-context-sync/MCP_SETUP|MCP 配置指南]]。

---

## 参与贡献

我们欢迎任何形式的贡献：

- **案例分享**: 你用 AI 完成了什么？效率提升了多少？
- **工具推荐**: 发现了好用的 AI 工具组合？
- **方法论改进**: 对现有内容有修正或补充？
- **问题反馈**: 发现了过时或错误的信息？

详见 [[CONTRIBUTING|贡献指南]]。

---

## 项目结构

```
ai_developer_growth/
├── GOVERNANCE.md               # 通用治理标准 (可复制到任何项目)
├── CLAUDE.md                   # Agent 系统指令 (强制遵守)
├── AGENTS.md                   # Agent 定义索引
├── UBIQUITOUS_LANGUAGE.md       # 领域术语表
├── CONTEXT.md                  # 项目上下文 (AI 需要读取)
├── INDEX.md                    # 知识地图入口
├── docs/
│   ├── MOC.md                  # 知识地图 (Map of Content)
│   ├── adr/                    # 架构决策记录
│   │   └── ADR.md              # ADR 聚合索引
│   ├── governance/             # 通用治理框架
│   │   ├── MAP.md              # 可视化地图
│   │   ├── CHEATSHEET.md       # 快速参考卡
│   │   ├── INSTALL.md          # 安装指南
│   │   └── languages/          # 语言特定规则 (13 种)
│   ├── frameworks/             # 框架特定规则 (11 种)
│   ├── devops/                 # DevOps 规范
│   ├── database/               # 数据库规范
│   ├── api/                    # API 设计规范
│   ├── security/               # 安全规范
│   ├── testing/                # 测试与工作流
│   ├── agent-dev/              # Agent 开发规范
│   ├── mindset/                # 认知升级
│   ├── learning/               # 学习方法
│   ├── efficiency/             # 工程效率
│   └── tools/                  # 工具选型
├── case-studies/               # 实践案例 (10 个)
├── examples/                   # 代码示例
│   ├── ai-context-sync/       # 知识验证工具
│   │   ├── src/
│   │   │   ├── cli/commands/   # CLI 命令模块
│   │   │   ├── providers/      # LLM 提供者 (7 文件)
│   │   │   └── handlers/       # MCP 处理器 (5 文件)
│   │   └── tests/              # 单元 + 集成测试
│   ├── self-correction-loop/
│   ├── multi-agent-orch/
│   │   └── tests/              # 集成测试
│   └── ai-task-prioritizer/
├── tests/                      # 根目录测试 (4 文件)
└── tools/scripts/              # 工具脚本
```

---

## Agent 开发治理

本项目定义了一套**通用的** Agent 开发规范，适用于任何项目。

### 通用治理标准

| 文件 | 用途 | 适用范围 |
|------|------|----------|
| `GOVERNANCE.md` | 完整的治理标准 | 任何项目 |
| `docs/governance/INSTALL.md` | 安装指南 | 任何项目 |
| `docs/governance/MAP.md` | 可视化地图 | 任何项目 |
| `docs/governance/CHEATSHEET.md` | 快速参考卡 | 任何项目 |

### 编程语言规范 (13 种)

| 语言 | 文件 | 用途 |
|------|------|------|
| Python | `docs/governance/languages/python.md` | Python 项目 |
| Rust | `docs/governance/languages/rust.md` | Rust 项目 |
| TypeScript | `docs/governance/languages/typescript.md` | TS 项目 |
| Go | `docs/governance/languages/go.md` | Go 项目 |
| Java | `docs/governance/languages/java.md` | Java 项目 |
| C# | `docs/governance/languages/csharp.md` | C# 项目 |
| Kotlin | `docs/governance/languages/kotlin.md` | Kotlin 项目 |
| PHP | `docs/governance/languages/php.md` | PHP 项目 |
| Ruby | `docs/governance/languages/ruby.md` | Ruby 项目 |
| C/C++ | `docs/governance/languages/cpp.md` | C/C++ 项目 |
| Swift | `docs/governance/languages/swift.md` | Swift 项目 |
| Scala | `docs/governance/languages/scala.md` | Scala 项目 |
| Elixir | `docs/governance/languages/elixir.md` | Elixir 项目 |

### 框架规范 (11 种)

| 框架 | 文件 | 用途 |
|------|------|------|
| React | `docs/frameworks/react.md` | React 项目 |
| Vue | `docs/frameworks/vue.md` | Vue 项目 |
| Angular | `docs/frameworks/angular.md` | Angular 项目 |
| Svelte | `docs/frameworks/svelte.md` | Svelte 项目 |
| Next.js | `docs/frameworks/nextjs.md` | Next.js 项目 |
| NestJS | `docs/frameworks/nestjs.md` | NestJS 项目 |
| Express/Fastify | `docs/frameworks/express.md` | Express 项目 |
| Flask | `docs/frameworks/flask.md` | Flask 项目 |
| Django | `docs/frameworks/django.md` | Django 项目 |
| FastAPI | `docs/frameworks/fastapi.md` | FastAPI 项目 |
| Spring Boot | `docs/frameworks/springboot.md` | Spring Boot 项目 |

### 领域规范

| 领域 | 文件 | 用途 |
|------|------|------|
| Docker | `docs/devops/docker.md` | 容器化最佳实践 |
| Kubernetes | `docs/devops/kubernetes.md` | K8s 部署与管理 |
| CI/CD | `docs/devops/cicd.md` | 持续集成/持续部署 |
| SQL | `docs/database/sql.md` | 关系型数据库 |
| NoSQL | `docs/database/nosql.md` | 非关系型数据库 |
| RESTful | `docs/api/rest.md` | REST API 设计 |
| GraphQL | `docs/api/graphql.md` | GraphQL API 设计 |
| gRPC | `docs/api/grpc.md` | gRPC API 设计 |
| 认证授权 | `docs/security/authentication.md` | 认证模式 |
| OWASP | `docs/security/owasp.md` | 安全风险防护 |
| 测试策略 | `docs/testing/strategy.md` | 测试最佳实践 |
| Git 工作流 | `docs/testing/git-workflow.md` | Git 分支规范 |

### 项目特定规范

| 规范 | 文件 | 用途 |
|------|------|------|
| Prompt 编写标准 | `docs/agent-dev/prompt-standards.md` | 如何编写高质量 agent 定义 |
| 开发流程 | `docs/agent-dev/workflow-standards.md` | 5 步闭环生命周期 |
| 质量门禁 | `docs/agent-dev/quality-gates.md` | 4 道门禁检查 |
| 上下文管理 | `docs/agent-dev/context-management.md` | CONTEXT/ADR/AGENTS 维护 |

### 项目特定规范

| 规范 | 文件 | 用途 |
|------|------|------|
| Prompt 编写标准 | `docs/agent-dev/prompt-standards.md` | 如何编写高质量 agent 定义 |
| 开发流程 | `docs/agent-dev/workflow-standards.md` | 5 步闭环生命周期 |
| 质量门禁 | `docs/agent-dev/quality-gates.md` | 4 道门禁检查 |
| 上下文管理 | `docs/agent-dev/context-management.md` | CONTEXT/ADR/AGENTS 维护 |

### 快速开始

**在你的项目中使用治理标准**:
```bash
# 复制通用标准到你的项目
cp GOVERNANCE.md /path/to/your/project/
cp docs/governance/INSTALL.md /path/to/your/project/docs/governance/

# 查看安装指南
cat docs/governance/INSTALL.md
```

**在本项目中使用**:
1. **阅读 `CLAUDE.md`** - 了解所有强制规范
2. **使用模板** - `docs/agent-dev/agent-prompt-template.md`
3. **遵循流程** - 需求→设计→编码→审计→沉淀
4. **通过门禁** - 每个 Gate 必须通过才能继续

### 质量门禁流程

```
Gate 1: Design Review → Gate 2: Implementation Review → Gate 3: Automated Audit → Gate 4: Documentation Review
```

CI/CD 自动执行 Gate 2-3 检查，Gate 1 和 Gate 4 需人工审查。

---

*AI 时代的竞争不是人与 AI 的竞争，而是掌握 AI 的人与不掌握 AI 的人的竞争。*

*Last Updated: 2026-07-17*
