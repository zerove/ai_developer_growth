---
title: 能力雷达集成指南
description: > 将 AI 时代开发者能力雷达集成到团队的核心人才流程中
category: 工具层
tags: ['AI', 'REST', 'Python', 'radar', '测试']
difficulty: 初级
reading_time: 10 分钟
updated: 2026-07-21
---

# 能力雷达集成指南

> 将 AI 时代开发者能力雷达集成到团队的核心人才流程中

---

## 📋 集成清单

| 场景 | 集成方式 | 频率 | 负责人 |
|------|----------|------|--------|
| **新员工入职** | 入职第 1 周完成评估 | 入职第 1 周 | 导师/HR |
| **季度复测** | 团队全员重测 | 每季度初 | 技术负责人 |
| **招聘筛选** | 面试前发送评估 | 面试前 | 面试官/HR |
| **晋升评估** | 晋升申请必附雷达图 | 晋升申请时 | 技术委员会 |
| **团队健康度** | 匿名聚合团队雷达 | 季度中 | 技术负责人 |
| **项目复盘** | 项目结束时团队雷达对比 | 项目结束 | 技术负责人 |

---

## 🎯 1. 新员工 Onboarding 集成

### 入职第 1 周清单

```markdown
# 新员工 Onboarding - 能力雷达评估

## 入职第 1 周任务
- [ ] Day 1: 完成环境搭建
- [ ] Day 2: 阅读 `examples/capability-radar/README.md`
- [ ] Day 3: 完成能力雷达自评 (约 15 分钟)
- [ ] Day 4: 与导师 1-on-1 复盘雷达结果
- [ ] Day 5: 制定个人成长 OKR (基于雷达最弱维度)

## 导师 1-on-1 复盘模板
- **雷达综合等级**: L__
- **最强维度**: __ (分数: __)
- **最弱维度**: __ (分数: __)
- **下季度重点提升**: 
- **导师建议资源**: 
```

### Onboarding 文档集成

在 `docs/efficiency/full-cycle-workflow.md` 中的 Onboarding 章节添加：

```markdown
## 新员工 Onboarding - 能力雷达基线建立

新员工入职第一周需完成 [能力雷达自评](examples/capability-radar/README.md)，
建立个人能力基线。导师需在第一周内完成 1-on-1 复盘，
基于雷达结果制定个性化成长计划。
```

---

## 🎯 2. 招聘筛选集成

### 面试流程集成

```markdown
# 面试流程 - 能力雷达前置评估

## 面试前 (候选人收到面试邀请后)
1. HR 发送能力雷达评估链接/附件
2. 候选人完成自评 (约 15 分钟)
3. 面试官收到雷达报告，作为面试参考

## 面试中
- 结合雷达结果设计针对性问题
- 重点验证候选人自评的高分维度
- 探究低分维度的真实水平

## 面试后
- 面试反馈中引用雷达维度
- 录用决策参考雷达综合等级
```

### 招聘 JD 模板集成

创建 `templates/jd-template.md`：

```markdown
# [职位名称] 招聘 JD

## 核心要求
- **能力雷达等级**: L2+ (AI 原生工程师) / L3+ (技术负责人)
- **必备维度**: 
  - [ ] 问题定义与产品思维 ≥ L2
  - [ ] 架构决策与系统设计 ≥ L2
  - [ ] AI 协作与提示工程 ≥ L2
  - [ ] 工程严谨性与质量文化 ≥ L2
  - [ ] 学习与知识内化 ≥ L2

## 加分项
- [ ] 任一维度达 L3+
- [ ] 有开源项目/技术博客/社区贡献
- [ ] 有团队技术领导经验

## 面试评估权重
- 代码能力: 30%
- 架构设计: 25%
- AI 协作能力: 20%
- 产品思维: 15%
- 文化匹配: 10%

## 面试官评分卡 (引用雷达维度)
| 维度 | 候选人自评 | 面试官评分 | 证据 |
|------|-----------|-----------|------|
| 问题定义与产品思维 | L__ | L__ |  |
| 架构决策与系统设计 | L__ | L__ |  |
| AI 协作与提示工程 | L__ | L__ |  |
| 工程严谨性与质量文化 | L__ | L__ |  |
| 学习与知识内化 | L__ | L__ |  |
```

---

## 🎯 3. 晋升通道集成

### 晋升评估表模板

创建 `templates/promotion-evaluation.md`：

```markdown
# 晋升申请 - 能力雷达评估

## 申请人信息
- 姓名: 
- 当前职级: L__
- 申请职级: L__
- 申请日期: 

## 能力雷达评估结果 (必填)

### 雷达图摘要
- **综合等级**: L__
- **最强维度**: 
- **最弱维度**: 

### 维度详细评分
| 维度 | 自评等级 | 评委评分 | 关键证据 |
|------|---------|---------|---------|
| 问题定义与产品思维 | L__ | L__ |  |
| 架构决策与系统设计 | L__ | L__ |  |
| AI 协作与提示工程 | L__ | L__ |  |
| 工程严谨性与质量文化 | L__ | L__ |  |
| 学习与知识内化 | L__ | L__ |  |

### 晋升门槛检查
- [ ] 当前职级 L2 → 申请 L3: 全维度 ≥ L2
- [ ] 当前职级 L3 → 申请 L4: 全维度 ≥ L3 且至少 1 维度 ≥ L4
- [ ] 当前职级 L4 → 申请 L5: 全维度 ≥ L4 且至少 2 维度 ≥ L5

### 关键产出佐证 (每个维度至少 1 个)
| 维度 | 代表性产出 | 链接/描述 |
|------|-----------|----------|
| 问题定义与产品思维 | PRD/ADR/OKR |  |
| 架构决策与系统设计 | ADR/架构文档 |  |
| AI 协作与提示工程 | Prompt Chain/工具/工作流 |  |
| 工程严谨性与质量文化 | ADR/测试覆盖率/CI配置 |  |
| 学习与知识内化 | 博客/分享/开源贡献 |  |

### 评委签名
| 角色 | 姓名 | 签名 | 日期 |
|------|------|------|------|
| 直属上级 |  |  |  |
| 技术委员会 |  |  |  |
| HRBP |  |  |  |
```

---

## 🎯 4. 团队健康度雷达

### 团队雷达收集脚本

创建 `scripts/team-radar-collect.py`：

```python
#!/usr/bin/env python3
"""
团队能力雷达匿名收集脚本
用于季度团队健康度评估
"""

import json
import os
from pathlib import Path
from datetime import datetime
from capability_radar.src.assessment import AssessmentEngine
from capability_radar.src.capability_model import Dimension, Level

def collect_team_radar(team_name: str, members: list):
    """收集团队成员雷达数据"""
    engine = AssessmentEngine()
    results = {}
    
    for member in members:
        print(f"\n--- {member} 的评估 ---")
        # 这里可以集成交互式评估或读取已有 JSON
        # 简化版：读取已有文件
        radar_file = Path(f"radar-data/{member}.json")
        if radar_file.exists():
            with open(radar_file) as f:
                results[member] = json.load(f)
    
    # 聚合团队雷达
    team_radar = aggregate_team_radar(results)
    
    # 保存团队报告
    report_dir = Path(f"radar-reports/{team_name}")
    report_dir.mkdir(parents=True, exist_ok=True)
    
    report_file = report_dir / f"team-radar-{datetime.now().strftime('%Y%m%d')}.json"
    with open(report_file, 'w') as f:
        json.dump({
            "team": team_name,
            "date": datetime.now().isoformat(),
            "members": len(results),
            "radar": team_radar,
            "individual": results
        }, f, indent=2, ensure_ascii=False)
    
    # 生成 Markdown 报告
    generate_team_report(team_radar, team_name, report_dir)
    
    print(f"✅ 团队雷达报告已生成: {report_file}")

def aggregate_team_radar(individual_results):
    """聚合团队雷达 (匿名平均)"""
    dimensions = ["product", "architecture", "ai_collab", "engineering", "learning"]
    aggregated = {}
    
    for dim in dimensions:
        scores = [r["dimension_scores"][dim] for r in individual_results.values()]
        aggregated[dim] = {
            "average": sum(scores) / len(scores),
            "min": min(scores),
            "max": max(scores),
            "distribution": {f"L{i}": scores.count(i) for i in range(5)}
        }
    
    return aggregated

def generate_team_report(team_radar, team_name, output_dir):
    """生成团队雷达 Markdown 报告"""
    lines = [
        f"# {team_name} 团队能力雷达报告",
        f"\n**生成时间**: {datetime.now().strftime('%Y-%m-%d')}",
        f"**参与人数**: {len(team_radar.get('individual', {}))}",
        "\n## 📊 团队雷达概览\n"
    ]
    
    for dim_name, data in team_radar.items():
        if dim_name == "individual":
            continue
        bar = "█" * int(data["average"] * 5) + "░" * (20 - int(data["average"] * 5))
        lines.append(f"- **{dim_name}**: {bar} {data['average']:.2f}")
    
    lines.extend([
        "\n## ⚠️ 团队短板识别",
        f"最弱维度: {min(team_radar, key=lambda k: team_radar[k]['average'])}",
        f"最强维度: {max(team_radar, key=lambda k: team_radar[k]['average'])}",
        "\n## 📋 建议行动",
        "1. 针对最弱维度安排专项培训",
        "2. 结对编程/Code Review 重点关注弱项",
        "3. 邀请内部专家分享强项经验",
    ])
    
    report_file = output_dir / f"team-radar-report-{datetime.now().strftime('%Y%m%d')}.md"
    report_file.write_text("\n".join(lines), encoding="utf-8")
    print(f"✅ Markdown 报告已生成: {report_file}")

if __name__ == "__main__":
    # 示例用法
    team_members = ["alice", "bob", "charlie", "diana"]
    collect_team_radar("backend-team", team_members)
```

---

## 🎯 5. CI/CD 集成

### GitHub Actions 自动化

创建 `.github/workflows/team-skill-assessment.yml`：

```yaml
name: Team Skill Assessment

on:
  schedule:
    - cron: '0 9 * * 1'  # 每周一上午 9 点
  workflow_dispatch:
    inputs:
      team:
        description: 'Team name'
        required: true
        type: string

jobs:
  team-assessment:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          
      - name: Install capability-radar
        run: pip install -e examples/capability-radar
        
      - name: Run team assessment
        run: |
          python scripts/team-radar-collect.py ${{ github.event.inputs.team || 'all' }}
          
      - name: Upload radar report
        uses: actions/upload-artifact@v4
        with:
          name: team-radar-report
          path: radar-reports/
          
      - name: Comment on PR/Issue
        if: github.event_name == 'workflow_dispatch'
        uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');
            const report = fs.readFileSync('radar-reports/${{ github.event.inputs.team }}/team-radar-report.md', 'utf8');
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: report
            })
```

---

## 📁 文件清单

创建以下文件结构：

```
ai_developer_growth/
├── templates/
│   ├── jd-template.md              # 招聘 JD 模板
│   ├── promotion-evaluation.md     # 晋升评估表
│   └── onboarding-checklist.md     # 入职清单
├── scripts/
│   ├── team-radar-collect.py       # 团队雷达收集脚本
│   └── radar-onboarding.py         # 入职雷达引导脚本
├── templates/
│   ├── radar-onboarding.md         # 入职雷达指引
│   ├── radar-promotion.md          # 晋升雷达指引
│   └── radar-hiring.md             # 招聘雷达指引
├── scripts/
│   └── team-radar-collect.py       # 团队雷达收集
├── .github/workflows/
│   ├── team-skill-assessment.yml   # 团队技能评估定时任务
│   └── case-study-validation.yml   # 案例验证
├── docs/
│   └── integration/
│       └── capability-radar-integration.md  # 本文档
└── examples/capability-radar/
    └── README.md                   # 已有完整文档
```

---

## ✅ 快速开始检查清单

- [ ] 创建 `templates/` 目录和模板文件
- [ ] 创建 `scripts/team-radar-collect.py` 团队收集脚本
- [ ] 创建 `.github/workflows/team-skill-assessment.yml` 定时任务
- [ ] 更新 `docs/efficiency/full-cycle-workflow.md` 添加雷达集成章节
- [ ] 更新 `docs/mindset/capability-model.md` 添加集成指南引用
- [ ] 运行 `python scripts/team-radar-collect.py` 验证团队收集
- [ ] 配置 GitHub Actions 定时任务
- [ ] 通知团队新流程上线

---

## 📚 相关文档

- [能力模型详细定义](../mindset/capability-model.md)
- [能力雷达工具文档](https://github.com/zerove/ai_developer_growth/tree/master/examples/capability-radar)
- [全周期工作流](../efficiency/full-cycle-workflow.md)
- [团队度量体系](../efficiency/metrics-framework.md)
- [代码审查指南](../efficiency/code-review-guide.md)

---

*最后更新: 2026-07-19 | 版本: 1.0*