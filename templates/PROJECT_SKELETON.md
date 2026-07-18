# 项目骨架模板 (PROJECT_SKELETON)

这是一个专为 AI 增强开发设计的现代项目结构模板。该结构旨在最大化 AI 的上下文理解能力，并确保项目的可维护性和可扩展性。

## 目录结构

```text
.
├── .ai/                    # AI 专用配置与指令 (例如: .cursorrules, jcode-config)
├── config/                 # 全局配置文件 (env, yaml, json)
├── docs/                   # 项目文档
│   ├── adr/                # 架构决策记录 (Architecture Decision Records)
│   │   └── 0001-xxx.md     # 决策文档
│   ├── specs/              # 功能规格说明书 / PRD
│   └── api/                # API 接口文档
├── scripts/                # 自动化脚本 (build, deploy, migrate)
├── src/                    # 源代码
│   ├── core/               # 核心业务逻辑
│   ├── api/                # 接口层 / 路由
│   ├── components/         # 可复用组件 / 模块
│   └── utils/              # 工具函数
├── tests/                  # 测试套件
│   ├── unit/               # 单元测试
│   ├── integration/        # 集成测试
│   └── e2e/                # 端到端测试
├── .gitignore              # Git 忽略文件
├── CONTEXT.md              # 🚀 项目上下文 (AI 同步核心文件)
├── README.md               # 项目概览与快速开始
└── CONTRIBUTING.md         # 贡献指南与代码规范
```

## 关键目录说明

### 1. `CONTEXT.md` (核心)
这是 AI 的“短期记忆”。记录当前进度、待办事项、关键术语和最近的决策。AI 在进入项目时应首先读取此文件。

### 2. `docs/adr/`
记录“为什么”这么做。AI 容易在迭代中丢失设计初衷，ADR 为其提供历史依据，防止回归错误的设计。

### 3. `.ai/`
存放针对 AI 代理的特定指令（Prompt）。例如：代码风格偏好、禁止使用的库、特定的重构模式。

### 4. `tests/`
采用分层测试结构。确保 AI 在生成代码后，能够快速运行对应的测试集进行验证。

---
*复制此结构以初始化你的 AI 增强开发项目。*
