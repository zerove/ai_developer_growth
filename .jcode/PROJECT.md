# AI Developer Growth - jcode Configuration

## Project Info
- **Name**: ai-developer-growth
- **Type**: Knowledge Base + Governance Framework
- **Language**: Python (tools) + Markdown (docs)
- **CI/CD**: GitHub Actions

## Agent Skills

本项目定义并注册了 4 个核心 agent skills：

| Skill | Command | Description | Script |
|-------|---------|-------------|--------|
| knowledge-curator | `/knowledge-curator` | 维护知识库结构、案例收集、文档质量 | `.jcode/scripts/knowledge-curator.py` |
| governance-auditor | `/governance-auditor` | 代码质量、安全、治理合规审计 | `.jcode/scripts/governance-auditor.py` |
| workflow-optimizer | `/workflow-optimizer` | 效率数据分析、工作流优化 | `.jcode/scripts/workflow-optimizer.py` |
| community-catalyst | `/community-catalyst` | 贡献流程管理、案例验证 | `.jcode/scripts/community-catalyst.py` |

## Skill 注册

Skills 已注册在 `.jcode/registry.json`，包含：
- **Actions**: 每个 skill 的可执行操作
- **Triggers**: 自动触发条件
- **Workflows**: 多 skill 组合工作流

## Hooks 配置

自动触发器已配置在 `.jcode/hooks.json`：
- **on_commit**: 提交时自动检查代码风格
- **on_pr**: PR 时运行完整审计
- **on_merge**: 合并后更新知识图谱
- **scheduled**: 定期执行维护任务

## Quick Commands

```bash
# Skill 执行
python .jcode/scripts/knowledge-curator.py scan
python .jcode/scripts/governance-auditor.py full
python .jcode/scripts/workflow-optimizer.py report
python .jcode/scripts/community-catalyst.py leaderboard

# 直接命令
ruff check .
ruff format --check .
mypy tools/scripts/ --ignore-missing-imports
python -m pytest tests/ -v --cov=tools/scripts

# 工具脚本
python tools/scripts/link_auditor.py .
python tools/scripts/validate_case_study.py --all
python tools/scripts/audit_to_pr.py --check-all
```

## Project Structure

```
ai_developer_growth/
├── .jcode/                    # jcode 配置
│   ├── PROJECT.md            # 本文件
│   ├── SWARM.md              # 多 Agent 协作配置
│   ├── hooks.json            # 自动触发器配置
│   ├── registry.json         # Skill 注册表
│   ├── skills/               # Skill 定义文档
│   └── scripts/              # Skill 可执行脚本
│       ├── knowledge-curator.py
│       ├── governance-auditor.py
│       ├── workflow-optimizer.py
│       └── community-catalyst.py
├── agents/                    # Agent 定义 (供参考)
├── case-studies/              # 实践案例 (15 个)
├── docs/                      # 方法论文档 (37 篇)
├── examples/                  # 代码示例 (6 个)
├── tools/scripts/             # 自动化工具脚本
├── tests/                     # 测试套件
└── .github/workflows/         # CI/CD
```

## Workflows

### PR Review Workflow
```bash
# 自动执行
governance-auditor → knowledge-curator → community-catalyst
```

### Weekly Maintenance Workflow
```bash
# 每周一 9:00 执行
governance-auditor → knowledge-curator → workflow-optimizer
```

### Release Prep Workflow
```bash
# 发布前执行
governance-auditor → knowledge-curator → workflow-optimizer → community-catalyst
```

## See Also

- `CLAUDE.md` - 项目完整指南
- `CONTRIBUTING.md` - 贡献指南
- `GOVERNANCE.md` - 治理标准
