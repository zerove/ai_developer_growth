# team-patterns Skill

分析代码库中的团队编码模式——命名风格、错误处理习惯、高频违规，自动生成自定义规则建议。

## Usage

```
/team-patterns                      # 分析团队编码模式
/team-patterns --output rules.yml   # 生成自定义规则文件
/team-patterns --quick              # 快速分析(只检测命名)
```

## Implementation

This skill runs:

```bash
python -c "
from pathlib import Path
from tools.scripts.rules_engine.pattern_learner import PatternLearner
patterns = PatternLearner().learn_from_directory(Path('.'))
for p in patterns:
    print(f'[{p.get(\"type\",\"pattern\")}] {p.get(\"message\", p.get(\"pattern\",\"\"))}')
    print(f'  置信度: {p.get(\"confidence\",0):.0%}')
"
```
