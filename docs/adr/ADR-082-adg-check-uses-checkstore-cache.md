# ADR-082: adg check 引入 CheckStore 文件级增量缓存

## 状态

接受

## 日期

2026-11-12

## 影响组件

- `tools/scripts/adg_cli/_cache.py`（新增：`FileCheckCache`、生效规则签名、issue 负载编解码）
- `tools/scripts/adg_cli/check.py`（`_check_files_parallel` 接入 worker 缓存、`_check_file_cached_worker`）
- `tools/scripts/adg_cli/commands/cmd/cmd_check.py`（`--cache` 开关、缓存 meta）
- `tools/scripts/adg_cli/parser.py`（`--cache` 参数）
- `tools/scripts/rules_engine/store.py`（`CheckStore.close()` 移出连接注册表）
- `tests/test_adg_check_cache.py`（新增契约测试）
- `tests/test_cache_observability_contract.py`、`tests/test_adg_jobs_resolution.py`（词汇表对齐）

## 背景

`docs/agent-dev/check-engine-contract-matrix.md` 的"收敛建议"第 4 条明确写着：

> 缓存能力的**执行路径**统一（而非仅字段统一）留待第二阶段：需先决定
> `adg check` 是否引入 `CheckStore`，该决策会改变 CLI 行为与磁盘产物，须单独立项。

第一阶段只统一了**字段词汇表**（`cache_supported` / `cache_engine` / `cache_reason` /
`cache_hits` / `cache_misses` / `cache_hit_rate`），执行路径仍分叉：

- `rules_engine.checker.check_directory(use_cache=True)`：真缓存（SQLite `CheckStore`），
  串行与并行都上报真实命中/缺失；
- `adg check`：显式声明 `cache_supported=false`、`cache_reason=adg_cli_path_no_rules_engine_cache`，
  所有计数为 `null` —— 即"知道自己没缓存"，但**没有缓存可用**。

后果是同一次全仓扫描走两条路时，未改动的文件被重复读取、重复匹配规则，耗时随
文件数线性增长；`adg check` 越是频繁调用，浪费越多。

## 决策

**`adg check` 引入文件级增量缓存，且缓存实现唯一**：

1. **复用 `rules_engine.store.CheckStore`**（同一张 `check_cache` 表），不新建第二套
   缓存实现 —— 两套实现必然漂移（字段、失效维度、并发语义都会分叉）。
2. **默认关闭**：只有显式 `--cache` 才启用。默认路径**不产生任何磁盘产物**，
   行为与第一阶段完全一致，避免"用户没要求却出现缓存文件 / 复用旧结果"。
3. **缓存键 = `(file_path, mtime, size, effective_rules_signature)`**：
   - 文件内容变化 → `mtime`/`size` 变 → 键不匹配；
   - **生效规则变化** → 签名变 → 键不匹配。

   签名取"最终生效规则集"（语言规则 + 框架规则 + custom rules + severity 覆盖）
   的规范 JSON 摘要，并**包含 severity 过滤档位** —— 该档位直接影响上报哪些
   issue，不进签名就会复用"另一个过滤档位下的结果"，造成漏报/多报。
4. **统计真实**：命中/缺失是真实计数；未启用或不可知一律 `null`（不臆造 0）；
   命中率 = `hits/(hits+misses)`，分母为 0 时为 `null`。
5. **缓存不改变结论**：命中缓存与完整检查产出的 issue 集合必须一致（契约测试锁定）。
6. **失败降级而非静默**：缓存读/写异常只退化为完整检查（**结论不受影响**），
   并计入 `cache_degraded`；用户显式要求缓存但存储不可用时，
   `cache_reason=cache_init_failed`（而不是假装"没缓存"）。
7. **串行与并行同源**：并行路径在 worker 进程内各打开一次缓存连接
   （SQLite WAL 下多进程并发写安全），命中/缺失/降级次数由父进程汇总，
   与串行路径语义一致。

### 配套修复：`CheckStore.close()` 必须移出连接注册表

`store.get_connection()` 按路径缓存连接，而 `CheckStore.close()` 只关连接、
**不清注册表**。于是同进程内第二次 `CheckStore(同一路径)` 会拿到**已关闭**的连接，
后续读写抛 `Cannot operate on a closed database` —— 表现为"缓存永远不命中"
（每次都退化成完整检查，且 `cache_degraded` 计数虚高）。
本次把 `close()` 改为调用 `close_connection()`（关闭 + 移出注册表），并加回归测试。

## 后果

### 正面

- `adg check --cache` 第二次及以后只重查改动过的文件，未改动文件直接复用；
- 缓存词汇表在三条路径上**语义一致**：`cache_supported` 恒为 `true`，
  `cache_engine` 恒为 `rules_engine_check_store`，差别只在 `cache_reason`
  （`cache_disabled` / `cache_init_failed` / `null`）；
- 契约矩阵中"adg check 无缓存能力"的结论被事实取代。

### 负面 / 代价

- `--cache` 会在项目目录下生成 `.adg/adg_check_cache.db`（可由 `[tool.adg].cache_db`
  改路径；仓库 `.gitignore` 已忽略 `*.db`）；
- `cache_supported` 由 `false` 变为 `true`，属于**可观测契约变更**，下游若依赖
  旧值需同步调整（本仓库已同步测试与矩阵）；
- 缓存是"按 mtime+size"判定，理论上存在同 mtime 同 size 但内容变化的极端情况
  （如 `git checkout` 回退到同大小文件且 mtime 被保留）；与 `rules_engine` 既有
  缓存采用同一判定维度，风险一致，不再引入新的失效模型。

## 修订记录

- 2026-11-12: 首次落地。新增 `tools/scripts/adg_cli/_cache.py`、`adg check --cache`
  开关与真实缓存统计；修复 `CheckStore.close()` 未移出连接注册表的缺陷；
  契约测试见 `tests/test_adg_check_cache.py`。
