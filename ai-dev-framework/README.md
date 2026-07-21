# AI Dev Framework - 通用治理框架

> 适用于任何项目的 AI Agent 开发治理标准。

## 特性

- ✅ **语言无关**: 支持 Python, TypeScript, Rust, Go, Java 等
- ✅ **框架无关**: 适用于任何框架
- ✅ **Agent 模板**: 预定义通用 Agent 角色
- ✅ **质量门禁**: 4 道门禁确保代码质量
- ✅ **自动化钩子**: 提交/PR/合并时自动触发

## 快速开始

### 1. 初始化项目

```bash
# 通用初始化
python ai-dev-framework/core/jcode_init.py my-project

# 指定语言和类型
python ai-dev-framework/core/jcode_init.py my-app --type webapp --language typescript

# 指定框架
python ai-dev-framework/core/jcode_init.py my-api --language python --framework fastapi
```

### 2. 生成的文件

```
your-project/
├── jcode.yaml              # 项目配置
├── AGENTS.md               # Agent 索引
├── GOVERNANCE.md           # 治理标准
├── .jcode/
│   ├── PROJECT.md          # 项目信息
│   └── hooks.json          # 钩子配置
└── agents/
    ├── code-guardian.md    # 代码守护者
    └── doc-curator.md      # 文档策展人
```

### 3. 自定义 Agent

```bash
# 编辑 Agent 定义
vim agents/code-guardian.md

# 添加新 Agent
vim agents/my-custom-agent.md
```

## 组件说明

### 1. 项目配置 (jcode.yaml)

```yaml
project:
  name: "my-project"
  type: "library"          # library, webapp, api, cli, knowledge-base
  language: "python"       # python, typescript, rust, go, java
  framework: "fastapi"     # 可选

  directories:
    source: "src"
    tests: "tests"
    docs: "docs"

  quality:
    min_test_coverage: 70
    lint_tool: "ruff"
    type_checker: "mypy"
    security_scanner: "bandit"
```

### 2. Agent 定义模板

#### code-guardian (代码守护者)

```yaml
agent-name: code-guardian
description: "维护代码质量、安全、风格一致性"

responsibilities:
  - "执行 lint 检查"
  - "运行测试套件"
  - "安全扫描"

instructions:
  - name: "lint-check"
    command: "{lint_tool} {source_dir}"
    validation:
      success: "exit_code == 0"
```

#### doc-curator (文档策展人)

```yaml
agent-name: doc-curator
description: "维护文档完整性、链接有效性"

responsibilities:
  - "检查文档链接"
  - "验证文档格式"
  - "更新索引"
```

### 3. 钩子系统

```json
{
  "hooks": {
    "on_commit": [
      {
        "name": "lint-check",
        "agent": "code-guardian",
        "action": "lint",
        "description": "提交时检查代码风格"
      }
    ],
    "on_pr": [
      {
        "name": "full-audit",
        "agent": "code-guardian",
        "action": "full",
        "description": "PR 时运行完整审计"
      }
    ],
    "scheduled": [
      {
        "name": "weekly-audit",
        "agent": "code-guardian",
        "action": "full",
        "schedule": "0 9 * * 1"
      }
    ]
  }
}
```

## 语言支持

| 语言 | Lint 工具 | 类型检查 | 测试工具 | 安全扫描 |
|------|-----------|----------|----------|----------|
| Python | ruff | mypy | pytest | bandit |
| TypeScript | eslint | tsc | vitest | semgrep |
| Rust | clippy | cargo | cargo test | cargo-audit |
| Go | golangci-lint | go vet | go test | gosec |

## 工作流程

### 标准开发流程

```
1. 编写代码
2. 提交 → 触发 lint-check
3. 创建 PR → 触发 full-audit
4. 合并 → 触发 update-index
```

### 质量门禁

| 门禁 | 检查内容 | 通过标准 |
|------|----------|----------|
| Gate 1 | Prompt 设计 | 人工审查通过 |
| Gate 2 | 代码质量 | Lint + 类型检查通过 |
| Gate 3 | 自动化审计 | CI/CD 流水线通过 |
| Gate 4 | 资产更新 | 文档同步完成 |

## 扩展

### 添加自定义 Agent

1. 创建 Agent 定义文件: `agents/my-agent.md`
2. 更新 AGENTS.md 索引
3. 在 hooks.json 中添加触发器

### 集成 CI/CD

```yaml
# .github/workflows/ci.yml
- name: Jcode Audit
  run: |
    python ai-dev-framework/core/jcode_init.py --validate
    ruff check .
    pytest tests/
```

## 相关文档

- [GOVERNANCE.md](../GOVERNANCE.md) - 治理标准
- [AGENTS.md](../AGENTS.md) - Agent 索引
- [agent-templates.md](agent-templates.md) - Agent 模板
