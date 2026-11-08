# 工具可观测性契约（hooks/ADG JSON）

> 目的：固定 `hooks_runner` / 规则检查 JSON 输出中缓存统计字段的语义，避免下游将 `0` 误判为“未使用缓存”。

## `hooks_runner.py language-rules --cache --format json`

输出包含顶层 `passed/path/files_checked/results` 与 `meta`：

| 字段 | 语义 |
|---|---|
| `meta.cache` | 本次命令是否走缓存路径（`--cache` 分支为 `true`） |
| `meta.cache_initialized` | 底层缓存存储是否成功初始化 |
| `meta.cache_hits` / `meta.cache_misses` | **启用缓存且可统计时**为真实计数（`int`）；**未启用缓存**时为 `null` |
| `meta.cache_degraded` | **启用缓存且可统计时**为降级次数（读/写/初始化回退等，`int`）；**未启用缓存**时为 `null` |
| `meta.parallel` / `meta.jobs` | 是否并行及有效 worker 数 |

### 规则引擎实现说明（`tools.scripts.rules_engine.checker.check_directory`）

- 串行与并行路径在启用缓存时均回传聚合后的 `cache_hits/cache_misses/cache_degraded`。
- 并行 worker 通过 `(result, cache_degraded, cache_hit)` 协议回传统计；`cache_hit`：`true` 命中、`false` 启用缓存但未命中、`null` 未启用缓存。
- **契约**：`null` 表示“未知/未启用”，不是 `0`。下游应将 `null` 与 `0` 区分处理。

## 相关测试

- `tests/test_adg_checker_refactor.py::TestCheckDirectoryStats`（含并行缓存 `miss -> hit`）
- `tests/test_checker_workers.py`（worker 协议与串并行一致性）
- `tests/test_store.py`（并行缓存集成）
