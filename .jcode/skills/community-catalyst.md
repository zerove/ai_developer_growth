# community-catalyst Skill

管理贡献流程、验证社区案例、设计贡献者激励机制

## Usage

```
/community-catalyst [action]
```

### Actions

- `triage` - 分流 Issues/PRs
- `validate` - 验证全部社区案例（等价 `validate_case_study.py --all`，不接收文件参数）
- `generate-adr <pr>` - 从 PR 生成 ADR（兼容 `--pr <pr>` 写法）
- `leaderboard` - 贡献者排行榜
- `stats` - 案例来源统计（内部 / 社区）

## Examples

```bash
# 分流 Issues
/community-catalyst triage

# 验证全部社区案例
/community-catalyst validate

# 从 PR 生成 ADR
/community-catalyst generate-adr 123

# 查看贡献者排行榜
/community-catalyst leaderboard

# 案例来源统计
/community-catalyst stats
```

## Implementation

This skill runs:

1. `tools/scripts/validate_case_study.py` - 案例验证
2. `tools/scripts/adr_generator.py` - ADR 生成
3. `tools/scripts/contributor_dashboard.py` - 贡献者分析

## Contribution Workflow

```
1. Fork 项目
2. 创建特性分支
3. 提交更改
4. 创建 PR
5. 等待审查
6. 合并
```

## Case Study Template

```markdown
# 案例标题

## 背景
项目背景描述

## 过程
实施过程

## 对比
| 指标 | Before | After |
|------|--------|-------|
| 效率 | 1x | 5x |

## 洞察
关键洞察

## 适用场景
适用场景描述
```
