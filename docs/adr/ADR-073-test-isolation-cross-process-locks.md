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
