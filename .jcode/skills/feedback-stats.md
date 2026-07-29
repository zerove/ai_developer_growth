# feedback-stats Skill

查看各规则的误报回馈统计——误报率最高的规则、已自动降级的规则、总反馈数。

## Usage

```
/feedback-stats              # 显示反馈统计
/feedback-stats --full       # 显示每条规则的详细数据
/feedback-stats --reset      # 重置所有反馈数据
```

## Implementation

This skill runs:

```bash
python -c "
from tools.scripts.rules_engine.feedback import get_feedback_stats
stats = get_feedback_stats()
print(f'总反馈数: {stats[\"total_feedback\"]}')
print(f'追踪规则: {stats[\"tracked_rules\"]}')
print(f'已降级规则: {stats[\"downgraded_rules\"]}')
"
```
