# AI Developer Growth - jcode 配置

>
> 合并自: PROJECT.md, USAGE.md, DEV_WORKFLOW.md, SWARM.md

---

## 项目信息

- **名称**: ai-developer-growth
- **类型**: 知识库 + 治理框架
- **语言**: Python (工具) + Markdown (文档)
- **CI/CD**: GitHub Actions
- **仓库**: https://github.com/zerove/ai_developer_growth

---

## 全局语言规则

**默认语言**: 中文 (zh-CN)，非必要不使用英文。

具体要求：
- 所有回复、注释、文档、提交信息使用中文
- 仅在代码标识符、API名称、技术术语等必须使用英文的场景下使用英文
- Git commit message 使用中文描述，如 `feat: 添加自动修复引擎`
- 代码注释使用中文，变量名和函数名保持英文
- 文档标题和内容使用中文

---

## Agent Skills (5 个)

| Skill | 职责 | 入口脚本 |
|-------|------|----------|
| knowledge-curator | 知识库、索引更新 | `.jcode/scripts/knowledge-curator.py` |
| governance-auditor | 代码质量、安全、治理合规审计 (v2.0) | `.jcode/scripts/governance-auditor.py` |
| governance-docs-validator | 治理层文档验证、索引引用完整性 | `.jcode/scripts/governance-docs-validator.py` |
| workflow-optimizer | 工作流分析、效率优化 | `.jcode/scripts/workflow-optimizer.py` |
| community-catalyst | 贡献流程管理、案例验证 | `.jcode/scripts/community-catalyst.py` |

### 共享模块

所有 skill 脚本共用 `.jcode/scripts/_common.py`:
- `run_command()` - 执行外部命令
- `print_check()` - 格式化输出检查结果
- `get_project_root()` - 获取项目根目录

### Hooks 执行引擎（两类 runner，职责不同）

- **门禁 CLI**：`tools/scripts/hooks_runner.py`（或 `python -m tools.scripts.hooks_runner`）—— 执行 lint/format/typecheck/test/security、quality-gate、doctor、ci-heartbeat、baseline 等开发/CI 门禁命令；由 Makefile、pre-push、CI 调用。
- **JCode 事件调度**：`.jcode/scripts/hooks_runner.py` —— 读取 `.jcode/hooks.json`，按 `on_commit/on_pr/on_merge/scheduled` 触发 skill actions；由 JCode/hooks 集成调用。

```bash
# JCode 事件调度示例
python .jcode/scripts/hooks_runner.py list
python .jcode/scripts/hooks_runner.py on_commit --files file1.py file2.md
python .jcode/scripts/hooks_runner.py on_pr

# 门禁 CLI 示例
.venv/bin/python -m tools.scripts.hooks_runner doctor
.venv/bin/python -m tools.scripts.hooks_runner typecheck
```

---

## 开发规范

### 代码风格
- Python: ruff (lint + format)
- 类型注解: mypy
- 测试: pytest

### 分支策略
- `main`: 稳定版本
- `feature/*`: 新功能
- `fix/*`: 修复

### 提交规范
```
type(scope): 中文描述

例如:
feat(rules): 添加 Kotlin 协程阻塞检测
fix(lsp): 修复类型注解错误
refactor(dashboard): 优化 FastAPI 路由
```

---

## 文档结构

```
docs/
├── tools/          # 工具文档
├── mindset/        # 思维方式
├── efficiency/     # 效率提升
├── monitoring/     # 监控运维
└── ROADMAP.md      # 路线图
```

---

*最后更新: 2026-07-26*
