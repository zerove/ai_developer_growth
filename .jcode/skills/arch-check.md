# arch-check Skill

分析项目模块依赖图，检测循环依赖、中心模块、分层违规等架构问题。

## Usage

```
/arch-check                # 分析当前项目架构
/arch-check --full         # 包含分层违规检查
/arch-check --output json  # JSON 格式输出
```

## Implementation

This skill runs:

```bash
python -c "
from pathlib import Path
from tools.scripts.rules_engine.arch import DependencyGraph
g = DependencyGraph()
issues = g.analyze_directory(Path('.'))
print(f'模块数: {g.module_count}, 依赖数: {g.edge_count}')
print(f'架构问题: {len(issues)} 个')
for i in issues:
    print(f'  [{i.severity}] {i.category}: {i.message}')
"
```
