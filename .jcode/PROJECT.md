# AI Developer Growth - jcode Configuration

## Project Info
- **Name**: ai-developer-growth
- **Type**: Knowledge Base + Governance Framework
- **Language**: Python (tools) + Markdown (docs)
- **CI/CD**: GitHub Actions

## Agent Skills

本项目定义并注册了 5 个核心 agent skills：

| Skill | Command | Description | Script |
|-------|---------|-------------|--------|
| knowledge-curator | `/knowledge-curator` | 维护知识库结构、案例收集、文档质量 | `.jcode/scripts/knowledge-curator.py` |
| governance-auditor | `/governance-auditor` | 代码质量、安全、治理合规审计 (v1.1) | `.jcode/scripts/governance-auditor.py` |
| governance-docs-validator | `/governance-docs-validator` | 治理层文档验证、索引完整性 | `.jcode/scripts/governance-docs-validator.py` |
| workflow-optimizer | `/workflow-optimizer` | 效率数据分析、工作流优化 | `.jcode/scripts/workflow-optimizer.py` |
| community-catalyst | `/community-catalyst` | 贡献流程管理、案例验证 | `.jcode/scripts/community-catalyst.py` |

## Skill Actions (v1.1 增强)

### governance-auditor 新增 Actions
- `validate-governance-docs` - 验证15个治理层文档格式完整性
- `check-ai-sdlc-compliance` - 检查 AI-SDLC 合规性
- `audit-hallucination-risks` - 审计幻觉风险（代码不安全模式 + 文档绝对化声明）

### governance-docs-validator Actions的 frontmatter、导航、内容结构
- `check-index` - 验证 GOVERNANCE.md、INDEX.md、CLAUDE.md 引用完整性
- `sync-refs` - 同步治理文档交叉引用

## Skill 注册

Skills 已注册在 `.jcode/registry.json`，包含：
- **Actions**: 每个 skill 的可执行操作
- **Triggers**: 自动触发条件
- **Workflows**: 多 skill 组合工作流

## Hooks 配置

自动触发器已配置在 `.jcode/hooks.json`：
- **on_commit**: 提交时自动检查代码风格 + 治理文档格式
- **on_pr**: PR 时运行完整治理文档验证
- **on_merge**: 合并后更新知识图谱
- **scheduled**: 定期执行维护任务 + 每月幻觉风险审计

## Quick Commands

```bash
# Skill 执行
python .jcode/scripts/knowledge-curator.py scan
python .jcode/scripts/governance-auditor.py full
python .jcode/scripts/governance-docs-validator.py full
python .jcode/scripts/workflow-optimizer.py report
python .jcode/scripts/community-catalyst.py leaderboard

# 治理文档验证
python .jcode/scripts/governance-docs-validator.py validate
python .jcode/scripts/governance-docs-validator.py check-index
python .jcode/scripts/governance-auditor.py validate-governance-docs
python .jcode/scripts/governance-auditor.py check-ai-sdlc-compliance
python .jcode/scripts/governance-auditor.py audit-hallucination-risks

# 直接命令
ruff check .
ruff format --check .
mypy tools/scripts/ ai-dev-framework/src --ignore-missing-imports
python -m pytest tests/ -v --cov=tools/scripts

# 工具脚本
python -m tools.scripts.link_auditor .
python -m tools.scripts.validate_case_study --all
python -m tools.scripts.audit_to_pr --check-all
```

## Project Structure

```
ai_developer_growth/
├── .jcode/                    # jcode 配置
│   ├── PROJECT.md            # 本文件
│   ├── SWARM作配置
│   ├── hooks.json            # 自动触发器配置
│   ├── skills/               # Skill 定义文档
│   │   ├── knowledge-curator.md
│   │   ├── governance-auditor.md
│   │   ├── governance-docs-validator.md
│   │   ├── workflow-optimizer.md
│   │   └── community-catalyst.md
│   └── scripts/              # Skill 可执行脚本
│       ├── knowledge-curator.py
│       ├── governance-auditor.py
│       ├── governance-docs-validator.py
│       ├── workflow-optimizer.py
│       └── community-catalyst.py
├── agents/                    # Agent 定义 (供参考)
├── case-studies/              # 实践案例 (15 个)
├── docs/efficiency/           # 方法论文档 (72+ 篇)
├── examples/                  # 代码示例 (10 个)
├── tools/scripts/             # 自动化工具脚本
├── tests/                     # 测试套件 (276 tests, 82% coverage)
└── .github/workflows-check)
```

## Workflows

### PR Review Workflow
```bash
# 自动执行
governance-auditor → governance-docs-validator → knowledge-curator → community-catalyst
```

### Weekly Maintenance Workflow
```bash
# 每周一 9:00 执行
governance-auditor → governance-docs-validator → knowledge-curator → workflow-optimizer
```

### Monthly Security Workflow
```bash
# 每月15日执行
governance-auditor (audit-hallucination-risks) → governance-docs-validator (full)
```

### Release Prep Workflow
```bash
# 发布前执行
governance-auditor → governance-docs-validator → knowledge-curator → workflow-optimizer → community-catalyst
```

## See Also

- `CLAUDE.md` - 项目完整指南
- `CONTRIBUTING.md` - 贡献指南
- `GOVERNANCE.md` - 治理标准
