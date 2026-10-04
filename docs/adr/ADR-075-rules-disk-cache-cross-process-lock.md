# ADR-075: 规则磁盘缓存必须跨进程加锁并原子写

## 状态

接受

## 日期

2026-10-04

## 影响组件

- `tools/scripts/rules_engine/rule_loader.py`（`_disk_cache_lock`、`_load_disk_cache_locked`、`_save_disk_cache_locked`、`load_rules`、`_CACHE_DIR_ENV`）
- `tests/test_rule_loader_cache_concurrency.py`（新增，4 个用例）
- `tests/conftest.py`（新增 `_isolate_rule_disk_cache` autouse fixture）
- `tests/test_pipeline_checker_ruleloader.py`（`TestDiskCache` 夹具隔离）

## 背景

ADR-073 收口后跑全量 `pytest -n 8`，观测到一次**真实**失败：

```
tests/test_pipeline_checker_ruleloader.py::TestDiskCache::test_save_and_load
AssertionError: assert 'python:abc' in {}
```

断言的含义是：刚写进去的 key，读回来时缓存里没有。这有两种可能 ——
磁盘缓存本身有缺陷，或测试在互相污染。本 ADR 分别查证了两者。

## 缺陷一：测试交叉污染（已观测并修复）

`TestDiskCache` 直接调用 `rl._save_disk_cache()` / `rl._load_disk_cache()`，
而 `_DISK_CACHE_FILE` 是模块级常量，硬编码在**仓库内**：

```
tools/.cache/rules_engine/rules_cache.json
```

同文件的 `test_rule_loader_disk_cache` 已正确 monkeypatch 到 `tmp_path`，
但 `TestDiskCache` 没有。于是 `-n 8` 下两个 worker 会往同一个真实文件里
互相覆盖：本用例写入 `{"python:abc": ...}`，另一 worker 随后用自己的
规则缓存整体覆盖，断言便看到空 dict。

这与被测代码无关，纯粹是测试写到了共享状态。已加 `autouse` fixture
把该类的缓存路径重定向到 `tmp_path`。

## 缺陷二：磁盘缓存的读-改-写竞态（本轮修复的主体）

`_DISK_CACHE_FILE` 在仓库内固定路径，且**所有进程共享**。原实现无任何
跨进程保护：

```python
disk_cache = _load_disk_cache()   # 读
...
disk_cache[cache_key] = result
_save_disk_cache(disk_cache)      # 整体覆盖写
```

### 症状 A：丢更新

两个并发写者各自「读出旧字典 → 加上自己的 key → 整体覆盖写回」，
后写者会把前写者的 key 静默抹掉。

以 6 个真实子进程并发调用 ``load_rules``（每个进程一个语言）实测：
去掉事务锁后每轮**丢 5 个 key**（只剩 1 个），5 轮全部如此；加锁后 5 轮
均**零丢失**。

注：更早一轮用**进程内多线程**做的探针报的是「60 次丢 53 次」「只锁
单个 IO 函数仍丢 4 次」。线程探针与真实场景差异明显（``flock`` 在同进程
内多线程共享 fd 与锁状态，见下方副作用范围），**应以子进程实测为准**。
那组线程数字不再作为决策依据。

### 症状 B：读到半截文件

`_save_disk_cache` 原先是裸 `write_text`，它先把文件截断为 0 字节再逐字
写入。并发读者会读到 0 字节或半截 JSON；更糟的是 `_load_disk_cache`
的 `except (json.JSONDecodeError, OSError)` 会把它**吞掉并返回空 dict**
—— 缓存静默失效，没有任何报错。实测 5 轮并发里有 **2 轮**读到损坏
JSON；单线程对照实验里，一次读 3349 次、损坏 10748 次。

## 缺陷三：测试污染面比一次偶发失败更大

修好上述用例后清空真实缓存、跑一次全量 `-n 8`，发现
`tools/.cache/rules_engine/rules_cache.json` 里多出 **7 个 key**，前缀为
`nonexistent` / `nonsense` / `test` / `python` / `rust` —— 全是测试遗留。

这意味着问题不止于“一次偶发失败”，还有两个持续危害：
- 下次真实跑 `adg check` 会命中这些用 `framework_dir=tmp_path` 生成的、
  仅对临时目录成立的规则缓存键；
- `-n 8` 下多个 worker 持续往同一文件写，交叉污染的**机会窗口**一直存在。

定位过程分三轮，每轮都推翻了上一轮的假设，记录在此以免重走：

1. 在 `conftest.py` 加 autouse fixture 只 monkeypatch
   `tools.scripts.rules_engine.rule_loader` → 跑完仍剩 **4 个 key**；
2. 二分定位到写入者是 `tests/test_rule_loader.py` 等文件，它们把
   `tools/scripts` 插入 `sys.path` 后用 `from rules_engine.rule_loader
   import ...` 导入，生成了**另一个模块对象**（独立的 `_DISK_CACHE_FILE`
   属性），monkeypatch 够不着。一并处理两个模块后 → 仍剩 **1 个 key**；
3. 逐文件扫描定位到 `tests/test_phase_runner_missing_path.py` 与
   `tests/test_semantic_degraded_visibility.py`：它们用
   `subprocess.run([sys.executable, hooks_runner.py, ...])` 跑真实 CLI，
   **in-process 的 monkeypatch 跨不过进程边界**。

最终解法：`_DISK_CACHE_DIR` 改为可用环境变量 `ADG_RULES_CACHE_DIR` 覆盖
（子进程天然继承），fixture 同时设该变量并 monkeypatch 两个模块对象。

该覆盖已直接验证（不只看“文件没被创建”）：带变量时
`_DISK_CACHE_DIR` 取变量值且 `load_rules` 正常落盘；不带变量时取仓库
默认路径；变量为空字符串时回退默认；变量指向不可写路径时**不抛异常**
（与既有 `except OSError` 行为一致）。
验证：全量 `-n 8` 通过，且真实缓存文件**全程未被创建**。

## 决策

### 缓存路径必须可被环境变量覆盖

见上文「缺陷三」。加锁解决的是**并发正确性**，隔离解决的是**谁在
写**；两者都要，缺一不可。

### 1. 锁必须是事务级的，不能只锁单个 IO 函数

先试了最直觉的做法：给 `_load_disk_cache` 加共享锁、给 `_save_disk_cache`
加独占锁。**这不够。** 因为两次取锁之间存在窗口：

```
load_rules:
  _load_disk_cache()   ← 取锁, 读到快照, 放锁
  ... 计算规则 ...
  _save_disk_cache()   ← 再取锁, 用**陈旧快照**覆盖写回
```

另一个进程可以在这两步之间完整地读写一轮。

**实测（6 个真实子进程并发，5 轮）**：

| 形态 | 最坏丢失 key 数 |
|------|----------------|
| 事务级锁（当前实现） | **0 / 6** |
| 只给两个 IO 函数各自加锁 | **5 / 6** |

即非事务形态几乎完全失效，锁形同虚设。故
`_load_disk_cache_locked` / `_save_disk_cache_locked` 是「调用方必须
已持锁」的内部实现，`load_rules` 直接在锁内调用它们。

### 2. 写盘必须原子

改为先写临时文件再 `os.replace()`。同一文件系统内的 rename 是原子的，
读者要么看到完整旧内容、要么看到完整新内容。

### 3. 锁文件放在系统临时目录，且按缓存目录派生

缓存目录本身会被整体清理。锁文件若放在里面，清理后锁文件消失 ——
已持 fd 的进程不受影响，但新进程会新建**另一个**锁文件，互斥失效。故
放在 `tempfile.gettempdir()` 下。

锁名由缓存目录路径的 sha1 前缀派生，而非固定一个名字。理由：锁的
作用域必须与它保护的数据一致。`ADG_RULES_CACHE_DIR` 允许不同调用方指向
不同缓存文件，此时它们本不该互相阻塞；固定锁名会把不相关的缓存退化成
全局串行（pytest 里每个测试都有自己的 tmp 缓存目录，固定锁会让它们白白
排队）。已验证：同一目录两次派生结果相同，不同目录派生结果不同。

### 4. 读用 `LOCK_SH`，写用 `LOCK_EX`

多个读者之间无冲突，不该把缓存退化成全局串行。

## 验证

### 全量门禁

- `pytest -n 8`：**5052 passed**（167s）；
- `ruff check` / `ruff format --check`：通过（469 文件）；
- `mypy tools/scripts/rules_engine/rule_loader.py`：no issues；
- ADR 索引、断链检查、治理文档校验、hooks doctor：全部通过。

### 污染根除验证

清空 `tools/.cache/` 后跑全量 `-n 8`，跑完真实缓存文件**未被创建**；
确认不带 `ADG_RULES_CACHE_DIR` 时 `load_rules("python")` 仍走默认路径并
正常写入（无回归）。

### 变异验证（两个不变量各自独立捕获）

回归测试锁两条不变量，每条用一个**独立变异**证明它真的有区分度：

| 变异 | 结果 | 捕获的用例 |
|------|------|-----------|
| 基线（已修复） | 4 passed（连跑 3 次） | — |
| 去原子 `os.replace`（保留锁） | 1 failed / 3 passed（连跑 3 次均捕获） | `test_reader_never_sees_torn_file` |
| 去事务锁（保留原子写） | 1 failed / 3 passed（连跑 3 次均捕获） | `test_concurrent_writers_keep_every_key` |

两次变异都只挂目标用例，另外 3 个对照保持通过。

### 测试设计上的两次返工（记录在此以免重犯）

第一版回归测试在子进程**退出前**读一次盘，判定是否损坏。变异后依然
`3 passed / 3 passed` —— 零区分度。原因是退出前写入早已结束，观测窗口
根本不存在。

第二版让专用读进程在写进程工作期间持续读，但写进程仍走 `load_rules`
写小载荷，「已截断但未写完」的窗口只有微秒级，变异A 又漏网
（实测 4 passed）。

最终版让大载荷写进程直接调**同一个生产函数** `_save_disk_cache`，
把窗口拉长到可观测，变异A 稳定 3/3 捕获。

### 健康对照

`test_single_threaded_behavior_unchanged` 确认锁未改变单线程语义：
保存后读回相等、覆盖写是替换而非合并、损坏 JSON 仍被吞成空 dict 而非
抛异常。`test_save_leaves_no_temp_files` 确认原子写结束后目录里只有
`rules_cache.json`，无临时文件残留。

### 副作用范围

锁路径为 `tempfile.gettempdir()` 下按缓存目录派生的
`adg-rules-disk-cache-<sha1前12位>.lock`，与仓库工作区无关；测试全部走
`tmp_path` 缓存目录，不触碰真实缓存。
用真实子进程而非线程，因为 `flock` 是进程级 advisory 锁，同进程内多线程
共享同一 fd 与锁状态，测不出跨进程语义（ADR-073 已踩过这个坑）。上文
「丢 5 个 key」的数字也正是因此才必须用子进程测。

锁路径改为派生后重跑两个变异，确认区分度未被削弱：变异A 去原子 rename
2/2 捕获撕裂读，变异B 去事务锁 2/2 捕获丢更新，每次均有 3 个对照通过；
还原后 4 passed。

## 与 performance 偶发失败的关系

排查 `test_optimized_check_directory_parallel` 偶发失败时，曾怀疑与本
缓存竞态相关。**已排除**：修复前的 `_load_disk_cache` 在读到损坏 JSON 时
返回空 dict，这只会导致缓存 **miss**（重新加载规则），不会抛异常，因而
不会让 worker 返回 `None` 或抛异常——而那正是结果变少的唯一两条分支。

该 performance flake 的触发条件**仍未定位**，见 `CONTEXT.md`
「未关闭的存量缺陷」。不得声称 ADR-075 解决了它。