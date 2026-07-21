# AI Developer Growth - jcode Configuration

## Project Info
- **Name**: ai-developer-growth
- **Type**: Knowledge Base + Governance Framework
- **Language**: Python (tools) + Markdown (docs)
- **CI/CD**: GitHub Actions

## Agent Skills

This project defines 4 core agent skills for knowledge base management:

| Skill | Command | Description |
|-------|---------|-------------|
| knowledge-curator | `/knowledge-curator` | 维护知识库结构、案例收集、文档质量 |
| governance-auditor | `/governance-auditor` | 代码质量、安全、治理合规审计 |
| workflow-optimizer | `/workflow-optimizer` | 效率数据分析、工作流优化 |
| community-catalyst | `/community-catalyst` | 贡献流程管理、案例验证 |

## Quick Commands

```bash
# Code quality
ruff check .
ruff format --check .

# Tests
python -m pytest tests/ -v --cov=tools/scripts

# Type check
mypy tools/scripts/ --ignore-missing-imports

# Link audit
python tools/scripts/link_auditor.py --check docs/ INDEX.md MOC.md

# Case validation
python tools/scripts/validate_case_study.py --scan case-studies/
```

## Project Structure

See `CLAUDE.md` for full project structure and guidelines.
