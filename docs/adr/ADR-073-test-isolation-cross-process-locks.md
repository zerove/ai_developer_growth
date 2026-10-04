# ADR-073: 测试改写受控仓库文件必须跨进程互斥，且优先做到不碰工作区

## 状态

接受

## 日期

2026-10-03

## 影响组件

- `tests/conftest.py`（`acquire_repo_mutation_lock`、`acquire_repo_read_lock`、`repo_mutating_file`、`restore_on_failure`）
- `tests/test_check_hooks_json_integrity.py`
- `tests/test_generate_adr_index.py`
- `tests/test_analyze_case_quality.py`

## 背景

收口阶段要求在 `-n 8` 下复现并行测试的偶发失败。复现结果是确定的
故障，不是环境抖动：

- `9 failed`；
- `.jcode/hooks.json` 里留下真实的 `ZZZ-canary` 字符串；
- `docs/adr/ADR.md` 也可能被并发写坏。

三类测试命中同一个根因：**被测代码把仓库相对路径写死了。**

- `check_hooks_json_integrity.sh` 内嵌 `HOOKS_JSON = ".jcode/hooks.json"`；
- `generate_adr_index.py` 内嵌 `docs/adr/ADR.md`；
- `analyze_case_quality.py` 按相对路径找 `INDEX.md` / `MOC.md`。

用例自身的 `addCleanup` 备份还原本身是**可靠的**，问题在于
pytest-xdist 下多个 worker 是独立**进程**，彼此看不到对方的
cleanup。于是 A 的还原会抹掉 B 正在用的 canary，B 的 canary 又会
让只读用例误判 —— 同一份受控文件被读写两方同时踩。

这类故障比普通测试不稳定危险得多：跑完的**工作区已被污染**，
此时直接提交就会把 `ZZZ-canary` 写进真实 hook 配置。

## 决策

### 1. 优先做到不碰工作区，而不是先上锁

`test_analyze_case_quality.py::test_cross_reference_checking` 原本在
仓库根写 `INDEX.md` / `MOC.md`，再在 `finally` 里
`Path("INDEX.md").unlink(missing_ok=True)`。锁定后改为
`monkeypatch.chdir(tmp_path)`：被测代码的**相对路径语义完全不变**，
但不再触碰工作区，也就不需要互斥锁。

顺带消掉一个更危险的后果：该用例一旦失败而 `finally` 未跑到，
或者仓库将来真的在根目录出现受控的 `INDEX.md`，这个 `unlink`
会**删掉真实文件**。改用 `tmp_path` 后这类风险从结构上不存在。

> 能靠环境隔离解决的，不要靠锁。锁是给"被测代码拒绝接受路径注入"
> 的用例兜底的。

### 2. 写者取独占锁，读者取共享锁

`hooks.json` 既被 `FailOpenDetectorTest` 真改写，也被
`SubcommandOptionTest` / `InterpreterConsistencyTest` 只读地跑真实
探测脚本校验。因此锁必须分两种：

| 角色 | 锁类型 | 理由 |
|------|--------|------|
| 改写受控文件的用例 | `LOCK_EX` | 同一时刻只允许一个 worker 写入 |
| 只读受控文件的用例 | `LOCK_SH` | 读者之间无写冲突，可并行 |

**只锁写者是不够的**，这是实测确认的：仅给写类加锁后 `-n 8` 仍剩
`2~3 failed`，且失败用例全部落在两个只读类上
（`test_runs_from_unrelated_cwd`、
`test_real_config_has_subcommand_hook_and_passes`）—— 它们在写者
持有 canary 的窗口里读到了临时内容。读者必须也被挡住。

用 `LOCK_SH` 而非对读者也用 `LOCK_EX`，是为了不把整份文件退化成
串行：读者之间本来就没有冲突。

### 3. 用 `fcntl.flock`，不用 xdist 分组

`loadgroup` / `xdist_group` 只在**同一 worker 内**分组，对"多个
worker 进程同时改同一文件"完全无效。`flock` 作用于文件本身，与
调度方式无关，`-n 4` 与 `-n 16` 同样安全。

锁文件放系统临时目录，不放仓库内 —— 否则会在工作区留下未跟踪
文件，而本仓库的收口流程以 `git status` 作为门禁之一。

### 4. 锁只管互斥，不管还原

备份还原仍由各用例自己的 `addCleanup` 负责。锁与还原职责不混：
锁解决"跨进程同时改"，cleanup 解决"异常路径也要还原"。

## 后果

### 正面

- `-n 8` 下 `9 failed` → `0 failed`，且连跑 4 次稳定；
- 全量 `-n 4` 与 `-n 8` 均为 `4603 passed`；
- 受控文件不再残留 canary；
- 新增约定可复用到后续所有"硬编码仓库路径"的测试。

### 后续补记（同源问题的第二、三批实例）

ADR 提交后继续全量跑，又暴露两处**同源**问题，均已按本 ADR 的
约定修复，故在此补记，避免后来者重复踩坑。

**实例 4：`test_link_auditor_supplement.py` 用固定相对名当工作目录**

三个类分别写死 `test_check_all` / `test_build_index` /
`test_check_edge`，都在**当前工作目录**下创建、`tearDown` 里
`shutil.rmtree`。pytest-xdist 下多个 worker 共享同一 cwd，于是
worker A 的 `tearDown` 会删掉 worker B 正在用的目录。实测 `-n 8`
下偶发 `FileNotFoundError: 'test_check_all'`，而失败落点是
`TestCheckAllLinks::test_check_all_handles_missing_dirs`，与真实原因
毫无关系。

改为每个用例用 `tempfile.TemporaryDirectory()`（唯一绝对路径）。
变异验证：换回固定相对名后 4 次运行分别 10/12/11/17 failed；
改回唯一临时目录后连跑 8 次全部 `69 passed`。

同一文件另有一处：`test_directory_mode_still_works` 在仓库根建
`.tmp_link_test` 并在 `finally` 里 `rmdir`。被测 CLI 接受路径参数，
改为 `tmp_path` 即可，完全不必写工作区。

**实例 5：`os.getcwd()` 作为还原点本身不可靠**

`TestCheckAllLinks.setUp` 原先记 `os.getcwd()` 供 `tearDown` 还原。
但若同 worker 的前一个用例把进程 cwd 留在一个**已被删除**的目录里
（`TemporaryDirectory.cleanup()` 会删掉当前工作目录），那么
`os.getcwd()` 自身就抛 `FileNotFoundError` —— `setUp` 第一行即失败。

实测确认：`os.chdir(tmp)` 后 `os.rmdir(tmp)`，再调 `os.getcwd()`
直接抛 `FileNotFoundError`。故还原点改用稳定的仓库根常量。

> 该实例只在实例 4 修好后才暴露出来 —— 目录名唯一化消除了互踩，
> cwd 泄漏才不再被掩盖。**一次只修一层，下一层才会显形。**

### 代价

- 被测代码拒绝路径注入时，相关用例被串行化。这是**正确**的代价：
  这些用例本就在改全局受控状态，并行跑没有意义。
- `tests/` 不在 mypy 门禁范围内（门禁只查 `tools/scripts/`），
  故 `tests/` 内存在缺失返回注解的存量函数。本次新增的 5 个函数
  已全部带注解，存量问题未在本 ADR 范围内处理。

## 验证方式

变异验证要求每处单独确认目标分支会变红：

| 变异 | 结果 |
|------|------|
| 仅移除读者共享锁（写者独占锁保留） | `-n 8` 复现 `2~3 failed` |
| 还原后连续 4 次 `-n 8` | 全部 `41 passed`，canary=0 |

健康代码对照：三组测试的其余用例在变异下保持绿，证明失败来自
共享锁这一处，而非测试整体被破坏。

## 后续加固：读者补齐 + 锁机制的确定性测试

首轮落地后仍有一批用例**只读**真实 `.jcode/hooks.json`（跑真实
脚本校验分发契约），它们与 `FailOpenDetectorTest` 并发时可能读到
写者窗口内的中间态，已全部接入 `acquire_repo_read_lock()`：

- `tests/test_jcode_hooks_runner.py`：抽出 `_read_real_hooks_json()`
  统一加锁读取，避免后续新增用例漏锁；
- `tests/test_jcode_scheduled_dispatch.py`：
  `test_real_config_dispatch_is_parseable`；
- `tests/test_governance_docs_validator.py`：
  `test_hooks_json_actions_are_supported`。

### 证据强度：必须诚实标注的一处局限

对上述读锁做变异验证时，**移除读锁后全量 `-n 8` 仍 4608 全绿**，
未能复现失败。原因是竞态窗口只存在于 `Path.write_text()` 的
截断重写阶段（微秒级），现有调度下采样概率极低。

因此：

- **不能**声称这些读锁"修好了"某次已复现的故障 —— 它们属于
  **预防性加固**：机制正确、代价极低，但缺少"移除即变红"的
  端到端证据。
- 为补上这层证据，新增 `tests/test_repo_lock_semantics.py`，
  **直接测 `conftest` 里真实的 `acquire_repo_*` 函数**（而非内联
  裸 `fcntl`），用子进程持锁一个确定时长来断言等待时长，不依赖
  运气。为此 `conftest._lock_path()` 支持 `ADG_TEST_LOCK_PATH`
  覆盖，使测试可指向 `tmp_path` 而不争用生产全局锁。

变异验证结果（全部被捕获）：

| 变异 | 结果 |
|------|------|
| `acquire_repo_read_lock` 退化为 no-op | `2 failed` |
| 读锁误用 `LOCK_EX`（应共享） | `1 failed` |
| `acquire_repo_mutation_lock` 退化为 no-op | `3 failed` |
| 锁路径写错（落进工作区） | `1 failed` |
| 全部还原 | `5 passed` |

> 踩过的坑，保留以免重犯：
> 1. 初版只测内联 `fcntl`，不测 conftest 真函数 —— "函数体改成
>    no-op"这种变异测不出来，等于白测。
> 2. 用"并发起 N 个短进程"验证共享锁不互斥 —— 短进程几乎不会
>    真正重叠，即便退化成独占也测不出来（变异 B 曾因此漏网）。
>    必须让一个读者**持续持锁**再探第二个。
> 3. 子进程用管道 `readline()` 做握手，在 pytest 捕获输出时
>    死锁（2 分钟挂起）。改用**文件标记**握手。
