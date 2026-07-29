# dashboard Skill

启动质量仪表盘——支持 Web 仪表盘、贡献者统计、质量趋势三种模式。

## Usage

```
/dashboard                              # 启动 Web 仪表盘(默认端口8765)
/dashboard start                        # 同上
/dashboard start --port 8080            # 指定端口

/dashboard contributor                  # 贡献者仪表盘
/dashboard contributor --format markdown
/dashboard contributor --format text

/dashboard trend                        # 质量趋势报告（含 sparkline）
/dashboard trend --sparkline            # 仅显示 sparkline 迷你趋势图
/dashboard trend --multi                # 多点趋势表格
/dashboard trend --lookback 20          # 查看最近 20 个快照
```

## Implementation

### `start` (Web 仪表盘)
```bash
python -m tools.scripts.rules_engine.dashboard
```

### `contributor` (贡献者仪表盘)
```bash
adg-dev dashboard contributor --path . --format {format}
```

### `trend` (质量趋势报告)
```bash
adg-dev dashboard trend --path . --lookback {lookback}
```

### `trend --sparkline` (迷你趋势图)
```bash
adg-dev dashboard trend --sparkline
```

### `trend --multi` (多点趋势表格)
```bash
adg-dev dashboard trend --multi --lookback {lookback}
```
