# quality-snapshot Skill

记录当前项目质量快照——错误数、警告数、文件数，存入质量趋势数据库并可查看历史变化。

## Usage

```
/quality-snapshot                    # 记录质量快照
/quality-snapshot --semantic         # 包含语义分析
/quality-snapshot --trend            # 显示历史趋势
```

## Implementation

This skill runs:

```bash
python -c "
from pathlib import Path
from tools.scripts.rules_engine.quality_trends import QualityTracker
tracker = QualityTracker()
snapshot = tracker.take_snapshot(Path('.'))
print(f'质量快照已记录:')
print(f'  文件: {snapshot.total_files}')
print(f'  问题: {snapshot.total_issues} (错误:{snapshot.errors}, 警告:{snapshot.warnings})')
report = tracker.generate_trend_report()
if report.has_regressions():
    for d in report.deltas:
        if d.direction == 'regressed':
            print(f'  ⚠️  {d.metric}: {d.previous} → {d.current}')
"
```
