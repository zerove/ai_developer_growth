# quality-snapshot Skill

记录当前项目质量快照——错误数、警告数、文件数，存入质量趋势数据库。
支持 sparkline 迷你趋势图和多点对比表格。

## Usage

```
/quality-snapshot                         # 记录质量快照 + 趋势摘要
/quality-snapshot --trend                 # 显示历史趋势（含 sparkline）
/quality-snapshot --multi                 # 多点趋势对比表格
/quality-snapshot --semantic              # 包含语义分析
/quality-snapshot --sparkline             # 仅显示 sparkline
```

## Implementation

### 默认（记录快照 + 摘要）
```bash
python -c "
from pathlib import Path
from tools.scripts.rules_engine.quality_trends import QualityTracker
tracker = QualityTracker()
snapshot = tracker.take_snapshot(Path('.'))
report = tracker.generate_trend_report()
print(tracker.generate_summary(report))
print()
print(tracker.format_trend_report(report))
"
```

### `--trend`（历史趋势 + sparkline）
```bash
python -c "
from pathlib import Path
from tools.scripts.rules_engine.quality_trends import QualityTracker
tracker = QualityTracker()
snapshot = tracker.take_snapshot(Path('.'))
print(f'Sparkline (issues): {tracker.generate_sparkline(\"total_issues\")}')
print(f'Sparkline (errors):  {tracker.generate_sparkline(\"errors\")}')
print()
report = tracker.generate_trend_report()
print(tracker.format_trend_report(report))
"
```

### `--multi`（多点对比表格）
```bash
python -c "
from pathlib import Path
from tools.scripts.rules_engine.quality_trends import QualityTracker
tracker = QualityTracker()
snapshot = tracker.take_snapshot(Path('.'))
print(tracker.generate_multi_trend_report())
"
```

### `--sparkline`（仅 sparkline）
```bash
python -c "
from tools.scripts.rules_engine.quality_trends import QualityTracker
tracker = QualityTracker()
print(f'Issues sparkline: {tracker.generate_sparkline(\"total_issues\")}')
print(f'Errors sparkline:  {tracker.generate_sparkline(\"errors\")}')
"
```
