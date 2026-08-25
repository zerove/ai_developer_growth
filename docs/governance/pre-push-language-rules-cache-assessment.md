# pre-push 阶段 language-rules 缓存评估结论（改进 G）

> 日期: 2026-08-25
> 背景: 11 项改进清单中的 G 项，评估 pre-push 本地 CI 是否应为 `language-rules` 检查接入增量缓存。

## 现状核实

- `.git/hooks/pre-push` 调用链: `hooks_runner.py lint → typecheck → test → quality-gate --full → baseline recompute`，
  **不直接调用** `language-rules`（已 grep 确认）；规则检查由 quality-gate 内部覆盖。
- 实测 `language-rules --path tools/scripts/rules_engine` 全量耗时 **2.8s**（147 文件），非推送瓶颈；
  推送链最重环节是全量测试（约 165s，xdist 并行）。

## 结论：保持全量检查，不接缓存

1. **正确性优先**: 规则签名缓存（改进 A 已落地）已保证规则变更时缓存键切换；但 language-rules 的
   检查结果还依赖基线豁免状态与文件间语义上下文，增量化引入的失效边界复杂度与 2.8s 的收益不成比例。
2. **瓶颈错位**: pre-push 总时长由 test 环节主导（占比 >98%），优化 language-rules 无感。
3. **风险不对称**: 推送前门禁是最后一道防线，任何缓存陈旧导致的漏检都会绕过本地 CI 直接进入远端。

## 若未来需要优化

- 优先方向是 test 环节的分片（CI 已有 sharding 先例）而非规则检查缓存；
- 或引入 `--changed-only` 显式参数（开发者手动选择快速模式），默认仍全量。
