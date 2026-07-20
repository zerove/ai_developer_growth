# 项目规范

本项目遵循 ai-dev-framework 治理标准。

## 快速开始

1. 阅读 `ai-dev-framework/core/GOVERNANCE.md`
2. 使用 `ai-dev-framework/core/templates/agent-prompt.md` 创建 agent
3. 通过 4 道质量门禁

## 工具集成

- opencode: hooks 已配置 (`ai-dev-framework/hooks/opencode/`)
- jcode: hooks 已配置 (`ai-dev-framework/hooks/jcode/`)
- pre-commit: 已安装 (`ai-dev-framework/hooks/pre-commit/`)

## 语言特定规则

见 `ai-dev-framework/languages/` 目录（13 种语言）

## 框架特定规则

见 `ai-dev-framework/frameworks/` 目录（11 种框架）

## 领域特定规则

- DevOps: `docs/devops/`
- 数据库: `docs/database/`
- API 设计: `docs/api/`
- 安全: `docs/security/`
- 测试与工作流: `docs/testing/`

## 项目特定规范

| 规范 | 文件 | 用途 |
|------|------|------|
| Prompt 编写标准 | `docs/agent-dev/prompt-standards.md` | 如何编写高质量 agent 定义 |
| 开发流程规范 | `docs/agent-dev/workflow-standards.md` | 5 步闭环生命周期 |
| 质量门禁 | `docs/agent-dev/quality-gates.md` | 各阶段质量检查标准 |
| 上下文管理 | `docs/agent-dev/context-management.md` | CONTEXT/ADR/AGENTS 维护规范 |
| Prompt 模板 | `docs/agent-dev/agent-prompt-template.md` | agent 定义的标准模板 |
| 质量检查清单 | `docs/agent-dev/quality-checklist.md` | 开发各阶段的检查项 |

## 验证命令

### 代码质量检查
```bash
# Lint + Format
make lint

# 测试
make test

# 全部检查
make check
```

### 文档一致性检查
```bash
# 断链检查
python tools/scripts/link_auditor.py

# 案例验证
python tools/scripts/validate_case_study.py case-studies/your-case.md

# 术语一致性
python tools/scripts/check_ubiquitous_language.py
```

### 治理框架检查
```bash
# 语言特定检查（自动检测语言）
bash ai-dev-framework/scripts/detect-language.sh
bash ai-dev-framework/core/quality-gates/scripts/check.sh

# 或指定语言
bash ai-dev-framework/core/quality-gates/scripts/check.sh python
```

## Agent 开发工作流

### 1. 需求分析
- 明确职责边界，与现有 agent 无重叠（查阅 `AGENTS.md`）
- 产出需求文档

### 2. Prompt 设计 (Gate 1)
- 基于 `docs/agent-dev/agent-prompt-template.md` 创建定义
- 命名: kebab-case
- 描述: 一句话核心职责
- 指令: 具体、可验证、含工具名/文件路径/函数名
- 工具: 最小权限（≤10个）
- 约束: 明确禁止行为
- 人工审查通过

### 3. 实现编码 (Gate 2)
- 遵循语言特定规范 (`ai-dev-framework/languages/{lang}/rules.md`)
- 代码风格: ruff/mypy/pytest (Python)
- 无 `unwrap()`/`expect()`/`as any` 等抑制
- 测试覆盖核心逻辑

### 4. 自动化审计 (Gate 3)
- CI/CD 自动执行: lint + type check + test + security scan
- 必须全部通过

### 5. 资产更新 (Gate 4)
- 更新 `AGENTS.md` 索引
- 更新 `CONTEXT.md` 项目状态
- 记录 `ADR.md` 关键决策
- 更新相关文档

## 禁止行为

- ❌ 硬编码密钥、密码、token
- ❌ 提交敏感信息到版本控制
- ❌ 无授权访问外部服务
- ❌ 执行高风险操作 (删除数据、重置系统)
- ❌ 使用 `unwrap()`/`expect()`/`as any`/`@ts-ignore` 在生产代码
- ❌ 跳过质量门禁
- ❌ 修改 trait/interface 签名而不审计所有实现者

## 必须行为

- ✅ 使用环境变量或密钥管理服务
- ✅ 最小权限原则
- ✅ 输入验证和输出编码
- ✅ 日志脱敏
- ✅ 更新 CONTEXT.md 后每次重大迭代
- ✅ 记录 ADR 于关键架构决策时
