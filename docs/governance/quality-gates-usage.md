---
title: 质量门禁使用指南
description: hooks_runner 生产化加固能力与命令速查
category: 治理层
tags: [质量门禁, hooks, CI]
difficulty: 中级
updated: 2026-08-25
---

# 质量门禁使用指南 (hooks_runner)

> 本文档记录 hooks_runner 的生产化加固能力：环境自检、基线棘轮、增量测试、台账分析。
> 最后更新: 2026-08-24

## 命令速查

```bash
# ── 环境自检 ──────────────────────────────────────────────
python tools/scripts/hooks_runner.py doctor
# 校验: git 仓库 / pre-commit 钩子健康(检测指向不存在 Python 的损坏钩子)
#       / ruff+mypy+pytest+bandit+pip-audit 可用性 / pytest 插件
#       / 基线文件结构 / hooks.json 可解析
# 必需项缺失退出码 1(CI 应失败)；插件缺失仅 ⚠️ 降级警告

# ── 基线棘轮管理 ──────────────────────────────────────────
python tools/scripts/hooks_runner.py baseline validate   # 结构校验(快速)
python tools/scripts/hooks_runner.py baseline recompute  # 重算对比(CI 防篡改)
# recompute 规则:
#   实际 > 基线 → 新增存量未入基线 → 失败(正常开发中会被棘轮拦截, 此处兜底)
#   基线 > 实际 → 基线过松 → 失败(防止人为放宽)
# 修复方式: 本地运行 quality-gate --full 刷新基线后提交

# ── 测试加速 ──────────────────────────────────────────────
python tools/scripts/hooks_runner.py test --incremental            # 只跑受变更影响的测试
python tools/scripts/hooks_runner.py test --incremental --base main # 指定基线分支
# 选择策略: tests/ 下文件直接收入; 同名约定(test_<stem>.py);
#           import 反查(测试文本含模块路径)。无法确定范围时保守提示回退全量

# ── 台账分析 ──────────────────────────────────────────────
python tools/scripts/audit_trends.py          # hash 链校验 + 类型统计 + 24h 异常告警
python tools/scripts/audit_trends.py --json   # JSON 输出(供 CI/看板消费)

# ── 运行历史维护 ──────────────────────────────────────────
python tools/scripts/hooks_runner.py db-maintain                     # 裁剪 90 天前的 quality_runs
python tools/scripts/hooks_runner.py db-maintain --retention-days 30 # 自定义保留窗口
# 行为: ISO 时间窗裁剪 quality_runs 及关联 file_results/rule_violations,
#       checkpoint + VACUUM 回收空间; 全部在保留期内时 noop(幂等)
# 接入: scheduled-governance.yml 每月 cron 自动执行

# ── 统计趋势采集 ──────────────────────────────────────────
python tools/scripts/update_stats.py --json            # 采集统计并输出 JSON
python tools/scripts/update_stats.py --check           # CI 模式: 漂移检测, 不一致退出码 1
python tools/scripts/update_stats.py --skip-quality-gate  # 快速模式: 跳过门禁采集
# 默认会调 quality-gate --full --format json 提取 gate_failed/gate_issues/
# gate_baseline_exempt/gate_pass_rate 四指标写入 .quality-trends/stats_history.jsonl;
# 门禁失败值本身也是趋势数据, 不算采集失败
```

## 配置项 ([tool.adg] in pyproject.toml)

| 配置 | 默认 | 说明 |
|------|------|------|
| `test_workers` | `"auto"` | pytest-xdist 并行数；`0` 禁用并行 |
| `test_reruns` | `2` | flaky 重试次数(pytest-rerunfailures)；`0` 禁用 |
| `cov_min` | `60` | 覆盖率门禁百分比(pytest-cov fail-under)；`0` 禁用 |
| `timeouts.{lint,format,typecheck,security,test}` | `300`/test=`900` | 各类别工具超时秒数 |

> 所有插件缺失时自动降级为串行/无重试/无覆盖率检查，不会导致门禁误报。

## 基线棘轮机制 (.jcode/baseline.json)

语义：

1. **无基线首次运行**：记录现状为起点，本次按严格模式判定（新文件的问题不会被豁免）
2. **已有基线**：存量问题豁免，只拦截新增问题——棘轮只紧不松
3. **通过时合并刷新**：已修复的存量问题移出基线；局部运行不覆盖未检查文件的计数
4. **失效清理**：全量运行后自动删除指向已删除文件的条目
5. **异常容错**：基线损坏时退回严格模式，不阻断门禁

基线文件随仓库分发（`.gitignore` 已豁免），CI 环境直接享受存量豁免。
测试通过 `JCODE_QUALITY_BASELINE` 环境变量隔离，不会污染真实基线。

## CI 集成 (.github/workflows/jobs/doctor-gate.yml)

- **doctor**: 三 OS matrix（ubuntu/macos/windows）冒烟验证工具链可用性，
  非 Linux 上基线路径格式差异仅告警不失败
- **baseline-guard**: 结构校验 + recompute 重算对比（Linux）
- **audit-trends**: 台账链完整性校验

Release 工作流在构建前强制运行 doctor 与 baseline validate。

## 故障排查

| 症状 | 处置 |
|------|------|
| `git commit` 报 pre-commit not found | 运行 `doctor` 定位；通常是钩子指向的 Python 不存在，`pre-commit uninstall && pre-commit install` 重装 |
| Test Suite 超时 | 检查 `[tool.adg].timeouts.test`(默认 900s)；确认 xdist 已安装 |
| recompute 大量不一致且路径带绝对前缀 | 确认从项目根目录运行；基线键是相对路径 |
| 基线豁免数异常下降 | 可能误删了 files 内容；`baseline recompute` 会指出差异，用 quality-gate --full 重建 |
