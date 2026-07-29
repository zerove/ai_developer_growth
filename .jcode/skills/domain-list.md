# domain-list Skill

查看当前项目已启用的领域规则包（金融/医疗/游戏等），以及各领域的规则详情。

## Usage

```
/domain-list                    # 列出已启用和可用的领域规则包
/domain-list --available        # 列出所有可用领域规则包
/domain-list --enable finance   # 启用金融领域规则
```

## Implementation

This skill runs:

```bash
python -c "
from pathlib import Path
from tools.scripts.rules_engine.rule_loader import load_domain_rules
rules = load_domain_rules(Path('.'))
print(f'已启用领域规则: {len(rules.get(\"anti_patterns\",[]))} 条')
import yaml, glob
for f in sorted(Path(\"ai-dev-framework/domains\").glob(\"*.yml\")):
    data = yaml.safe_load(f.read_text())
    print(f'  {f.stem}: {len(data.get(\"anti_patterns\",[]))} 条规则')
"
```
