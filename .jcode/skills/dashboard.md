# dashboard Skill

启动本地质量仪表盘 Web 服务，显示质量趋势图、历史对比、CI 质量摘要。

## Usage

```
/dashboard                   # 启动仪表盘(默认端口8765)
/dashboard --port 8080       # 指定端口
/dashboard --ci-data-dir .quality-trends  # 加载CI数据
```

## Implementation

This skill runs:

```bash
python -m tools.scripts.rules_engine.dashboard
```
