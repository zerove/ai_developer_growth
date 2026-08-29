---
title: "AI 开发环境配置标准 (AI Dev Environment Configuration)"
description: 面向 AI 辅助开发的 IDE、工具和工作区配置标准
category: 治理层
tags: ['AI', 'IDE', 'configuration', 'environment', 'governance']
difficulty: 进阶
reading_time: 10 分钟
updated: 2026-07-22
---

# AI 开发环境配置标准 (AI Dev Environment Configuration)

> 正确的环境配置是 AI 辅助开发效率的基础。

---

## 1. 核心原则

1. **最小配置**: 只配置必要的 AI 工具
2. **统一团队**: 团队使用一致的配置
3. **可复制**: 配置可版本控制和共享
4. **隐私优先**: 敏感信息不提交到版本控制

---

## 2. IDE 配置标准

### 2.1 推荐 IDE 配置

| IDE | 适用场景 | AI 集成 | 推荐度 |
|-----|----------|---------|--------|
| **Cursor** | 全栈开发 | 原生 AI | ⭐⭐⭐⭐⭐ |
| **Zed** | 高性能编辑 | AI 补全 | ⭐⭐⭐⭐ |
| **VS Code + Continue** | 通用开发 | 插件 AI | ⭐⭐⭐⭐ |
| **JetBrains + AI** | Java/Kotlin | 插件 AI | ⭐⭐⭐ |

### 2.2 必需配置项

```json
// .vscode/settings.json (团队共享)
{
  "editor.formatOnSave": true,
  "editor.codeActionsOnSave": {
    "source.fixAll": true,
    "source.organizeImports": true
  },
  "python.linting.enabled": true,
  "python.linting.ruffEnabled": true,
  "python.linting.mypyEnabled": true,
  "typescript.tsdk": "node_modules/typescript/lib"
}
```

### 2.3 AI 补全配置

```json
// 禁止 AI 补全的文件类型
"ai.suggestion.ignoreFiles": [
  "*.lock",
  "*.min.js",
  "*.min.css",
  "package-lock.json",
  "yarn.lock",
  "poetry.lock"
]
```

---

## 3. 工具链配置

### 3.1 Python 项目

```toml
# pyproject.toml
[tool.ruff]
line-length = 88
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "UP", "S"]
ignore = ["E501"]

[tool.mypy]
python_version = "3.12"
strict = true
warn_return_any = true

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-v --cov=src --cov-report=term-missing"
```

### 3.2 TypeScript 项目

```json
// tsconfig.json
{
  "compilerOptions": {
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "exactOptionalPropertyTypes": true
  }
}
```

### 3.3 Rust 项目

```toml
# clippy.toml
msrv = "1.75"

# rustfmt.toml
max_width = 100
tab_spaces = 4
```

---

## 4. Git Hooks 配置

### 4.1 Pre-commit 钩子

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-json

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.3.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
```
交信息规范

```
<type>(<scope>): <description>

类型:
  feat:     新功能
  fix:      Bug 修复
  docs:     文档更新
  style:    代码格式 (不影响功能)
  refactor: 重构
  test:     测试
  chore:    构建/工具

AI 生成代码额外标记:
  feat(ai): 新功能 (AI 生成)
  fix(ai):  Bug 修复 (AI 辅助)
```

---

## 5. 环境变量管理

### 5.1 必需的环境变量

```bash
# .env.example (提交到版本控制)
OPENAI_API_KEY=your-key-here
ANTHROPIC_API_KEY=your-key-here
# AI 模型配置
AI_MODEL=claude-4
AI_TEMPERATURE=0
AI_MAX_TOKENS=4096
```

### 5.2 禁止提交的信息

| 信息 | 原因 | 替代方案 |
|------|------|----------|
| API 密钥 | 安全风险 | 环境变量 |
| 数据库密码 | 安全风险 | 环境变量 |
| 私有证书 | 安全风险 | 环境变量 |
| 个人配置 | 一致性 | 团队配置 |

---

## 6. 团队配置共享

### 6.1 版本控制的配置

```
✅ 提交到 Git:
├── .vscode/settings.json (团队共享)
├── .pre-commit-config.yaml
├── pyproject.toml / tsconfig.json / Cargo.toml
├── .env.example (模板)
└── .editorconfig

❌ 不提交到 Git:
├── .env (实际配置)
├── .vscode/*.code-workspace (个人)
└── node_modules/ / __pycache__/
```

### 6.2 新成员入职清单

- [ ] 安装推荐 IDE
- [ ] 安装 AI 插件/配置
- [ ] 复制 `.env.example` → `.env`
- [ ] 运行 `pre-commit install`
- [ ] 验证 Linter 工作正常
- [ ] 验证 AI 补全工作正常

---

## 📂 导航

- [IDE 最佳实践](../tools/ide-best-practices.md) - IDE 配置详解
- [CI/CD 工作流](ci-cd-workflow.md) - 自动化配置
- [AI 模型选型与评估标准](ai-model-selection.md) - 模型选择

---

*本标准随工具演进持续更新。最后更新: 2026-07-22*

---

## 导航

**分类**: 治理层

**相关文档
- [[../GOVERNANCE|通用治理标准]]
- [[../GOVERNANCE|通用治理标准]]**:

- [[docs/efficiency/ai-code-generation-quality|代码质量]]
- [[docs/efficiency/ai-model-selection|模型选型]]
- [[docs/efficiency/ai-sdlc|SDLC]]
- [[docs/efficiency/ai-code-review-checklist|代码审查]]
- [[docs/efficiency/ai-nondeterministic-testing|非确定性测试]]


## 相关案例

- **相关案例**: [api-design-implementation](../case-studies/api-design-implementation.md)

- **相关案例**: [legacy-system-refactoring](../case-studies/legacy-system-refactoring.md)

- **相关案例**: [ml-model-deployment](../case-studies/ml-model-deployment.md)

- **相关案例**: [microservice-architecture](../case-studies/microservice-architecture.md)

- **相关案例**: [api-monitoring](../case-studies/api-monitoring.md)

- **相关案例**: [aiops-automation](../case-studies/aiops-automation.md)

- **相关案例**: [realtime-data-processing](../case-studies/realtime-data-processing.md)

- **相关案例**: [api-doc-generation](../case-studies/api-doc-generation.md)

- **相关案例**: [production-debugging](../case-studies/production-debugging.md)

- **相关案例**: [legacy-refactoring](../case-studies/legacy-refactoring.md)

- **相关案例**: [code-review-system](../case-studies/code-review-system.md)

- **相关案例**: [security-audit](../case-studies/security-audit.md)

- **相关案例**: [technical-documentation](../case-studies/technical-documentation.md)

- **相关案例**: [data-pipeline](../case-studies/data-pipeline.md)

- **相关案例**: [governance-self-audit](../case-studies/governance-self-audit.md)

- **相关案例**: [automated-testing-platform](../case-studies/automated-testing-platform.md)

- **相关案例**: [data-migration](../case-studies/data-migration.md)

- **相关案例**: [ai-context-sync-development](../case-studies/ai-context-sync-development.md)

- **相关案例**: [database-performance-optimization](../case-studies/database-performance-optimization.md)

- **相关案例**: [mobile-app-development](../case-studies/mobile-app-development.md)

- **相关案例**: [api-design](../case-studies/api-design.md)

- **相关案例**: [ai-task-prioritizer](../case-studies/ai-task-prioritizer.md)

- **相关案例**: [unit-testing](../case-studies/unit-testing.md)

- **相关案例**: [devops-pipeline](../case-studies/devops-pipeline.md)

- **相关案例**: [database-migration](../case-studies/database-migration.md)

- **相关案例**: [adg-dogfooding-search-pipeline](../case-studies/adg-dogfooding-search-pipeline.md)

- **相关案例**: [cli-tool-development](../case-studies/cli-tool-development.md)

- **相关案例**: [web-scraping-tool](../case-studies/web-scraping-tool.md)

- **相关案例**: [frontend-performance-optimization](../case-studies/frontend-performance-optimization.md)

- **相关案例**: [intelligent-customer-service](../case-studies/intelligent-customer-service.md)

- **相关案例**: [security-vulnerability-fix](../case-studies/security-vulnerability-fix.md)

