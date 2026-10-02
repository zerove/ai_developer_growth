# ADR-062: fail-open 检测器必须校验"可执行性"，而非匹配错误关键词

## 状态
接受

## 日期
2026-10-02

## 背景

Phase 30 建立了 `tools/scripts/check_hooks_json_integrity.sh`，用于在 `on_commit`
阶段发现"看似在工作、实际永远失败"的 hook（fail-open）。它诞生的起因是
`update-moc` hook 调用 `link_auditor.py --update-moc`，而该脚本根本没有这个参数，
hook 一直失败，却长期被其他 hook 的成功掩盖。

该脚本的旧实现方式是：运行 `hooks_runner`，然后在输出里 grep
`unrecognized arguments` 关键词。

本轮审计其余 skill 入口的 fail-open 状况时，顺带对该**检测器本身**做了变异测试，
结果发现它有两处结构性问题。

### 问题 1：判据过窄，只覆盖一种失败形态

旧实现只在出现 `unrecognized arguments` 时告警。而 fail-open 的形态远不止这一种：

| 故障形态 | 旧实现能否发现 |
|----------|----------------|
| `command` 参数不被支持（update-moc 历史 bug） | 能 |
| `skill` 存在但 `action` 拼错 | **不能** |
| `command` 指向的脚本不存在 | **不能** |
| `skill` 脚本本身不存在 | **不能** |

实测（注入 canary hook）：

```
变异 badarg    退出码=1  ✅ 捕获
变异 badaction 退出码=0  ❌ 漏检 —— 报告"全部 hook 命令参数识别正常"
变异 badscript 退出码=0  ❌ 漏检
```

### 问题 2：异常被静默吞掉

内嵌 Python 里有 `except Exception: pass`，且对 `hooks_runner` 设了 120s 超时。
一旦子进程超时或抛异常，脚本会跳过该 phase 并最终报"✅ 通过"。
换言之，**在慢环境下这个门禁会静默失效**。

值得注意的是：`hooks_runner` 本身并没有 fail-open —— 它正确地按 `returncode != 0`
判定，并在 `--files` 后无参数时显式 `sys.exit(1)`（那里已经有一处同类问题的修复注释）。
所以旧检测器的漏检不是因为底层判定错，而是因为它**只抽查一种错误文案**。

## 决策

把检测口径从"匹配错误关键词"改为"**校验 hook 指向的东西是否真的可执行**"，
具体分三类判定：

1. **command 指向的脚本必须存在**
2. **command 里的长选项必须在目标脚本的 `--help` 声明中**（含各子命令）
3. **skill/action 组合必须存在**：脚本文件存在，且 `action` 出现在脚本的
   `actions` / `action_map` 字面量里

不实际执行业务逻辑（会触发真实 lint / 全量测试，代价过高），只验证
"这个 hook 指向的东西存在且认识这个参数"。

同时把 `except Exception: pass` 换成显式报错：探测超时或无法执行时，
**报告问题而非静默跳过**。

## 实现中的两个坑（均由变异测试暴露）

### 坑 1：不能用 `<args> --help` 探测

最初实现是"把 command 的参数原样加上 `--help` 跑一遍，看是否报错"。
这看起来最直接，但 argparse 遇到 `--help` 会**先打印帮助并以 0 退出**，
根本不校验其余参数。实测：

```
$ python tools/scripts/link_auditor.py . --update-moc --help
options:
  -h, --help  ...
  --check-all  ...
退出码: 0        # 坏参数完全没被发现
```

这比旧实现更差 —— 它把原来能抓的 `badarg` 也变成了漏检。改为从 `--help`
输出里**解析出支持的选项**，再与 command 里的长选项逐一比对。

### 坑 2：只看顶层 `--help` 会产生假阳性

改用选项比对后，真实配置立刻报错：

```
❌ on_pr/self-correction: command 参数 --target 不被
  .jcode/scripts/self-correction-loop.py 支持 (可用: --help)
```

但这个 hook **完全可用**。原因是 argparse 的子命令选项不出现在顶层 usage 里：
`self-correction-loop.py` 顶层只暴露 `{run,validate}`，而 `--target` / `--tests`
属于 `validate` 子命令。

若不处理，门禁会把一个正常工作的 hook 拦下 —— **假阳性比漏检更糟**。
改为从顶层 usage 的 `{a,b,c}` 里枚举子命令，合并各子命令的选项集合。

### 附带修复：方括号导致选项解析整体失效

实现选项解析时，第一版写成"先判断 `token.startswith('--')` 再 strip 方括号"，
但 argparse 的 usage 行形如 `[--check-all]`，token 以 `[` 开头，
于是被判否、解析出**空集合** —— 参数校验整体静默失效（比显式报错更隐蔽）。
正确顺序是先 `strip('[]')` 再判断前缀。

### 补记：探测解释器必须与项目一致

初版探测用 `sys.executable`，即**跑这个 shell 脚本的解释器**（系统 `python3`）。
本机实测存在版本分叉：

```
$ python3 -V            # PATH 里的（mise 装的）
Python 3.14.7
$ uv run python -V      # 项目 venv
Python 3.11.15
```

若目标脚本依赖 venv 里的第三方包，用系统解释器探测会因 `ImportError`
拿不到 `--help`，于是 `supported` 为空 → **静默跳过参数校验**。
这正是本 ADR 要消灭的那类 fail-open，却在修复过程中被重新引入。

改为先选定项目解释器再探测：优先 `uv run python`，其次 `.venv/bin/python`，
最后才回退到 `PATH` 里的 `python3`。可用环境变量 `PY` 覆盖（便于测试回退路径）。

本机当前实测两种解释器探测结果一致（4 个脚本的 `--help` 均 rc=0），
所以这个缺陷尚未实际发作 —— 但它是一个**尚未引爆的**同类问题，
按“宁可漏检不可误伤”的对称原则也应修：宁可多花一次 `uv` 启动时间。

## 后果

- 检测器从 11s 降到 0.77s（旧实现要真跑 `on_commit` / `on_merge` 两轮 hook）
- 四类 fail-open 均可捕获，真实配置零误报
- 回归测试 `tests/test_check_hooks_json_integrity.py`（12 个用例）用 canary
  注入真实故障，确保修复不被静默回退

## 验证

### 真实接受路径（非自定义测试）

单测只能证明函数行为，不能证明门禁真的会拦住提交。因此直接走真实链路：

```
$ uv run python .jcode/scripts/hooks_runner.py on_commit --files .jcode/hooks.json
...
❌ [失败] hooks-json-integrity-check
  - on_commit/ZZZ-real-canary: skill 'knowledge-curator' 不支持 action 'no-such-action'
❌ 1 个 hooks 失败
退出码: 1        # 会阻断 git commit
```

### 与修复前版本的对照

对同一 canary 分别跑两个版本（`b47a124` 为修复前）：

| 版本 | 退出码 | 输出 |
|------|--------|------|
| 修复前（关键词匹配） | **0** | “✅ 全部 hook 命令参数识别正常” |
| 修复后（可执行性校验） | 1 | 明确指出不支持的 action |

即：**修复前的门禁对一个运行时确实失败的 hook 报绿灯**。
这是本次改动价值的直接证据。

### 环境无关性

| 场景 | 结果 |
|------|------|
| 仓库根目录 | 通过 |
| `/tmp` 下调用 | 通过（脚本自行 cd 到仓库根） |
| `PY=python3` 强制回退系统解释器 | 通过 |
| `PATH=/usr/bin:/bin`（无 uv） | 通过 |

### 变异测试

注入 canary 后确认退出码为 1：

| 变异 | 退出码 | 结果 |
|------|--------|------|
| `badarg`（`link_auditor.py --update-moc`） | 1 | 捕获 |
| `badaction`（`knowledge-curator no-such-action`） | 1 | 捕获（旧实现漏检） |
| `badscript`（`tools/scripts/ghost.py`） | 1 | 捕获（旧实现漏检） |
| `badskill`（`skill: ghost-skill`） | 1 | 捕获（旧实现漏检） |
| `clean`（真实配置） | 0 | 通过，零误报 |

对**测试本身**再做变异，确认它们不是装饰性断言：

- 退回关键词匹配实现 → 2 个真实配置测试失败
- 还原方括号 bug → `test_supported_long_options_parses_usage` 失败
- 退回 `sys.executable` → `test_script_prefers_project_interpreter_over_path_python` 失败

## 已知局限

- 非 argparse 的脚本（自定义参数解析、`sys.argv` 手写）无法从 `--help` 解析出选项，
  此时**跳过参数校验**（只校验脚本存在）。宁可漏检不可误伤。
- `.sh` 脚本同理跳过参数校验。
- action 校验依赖脚本里 `actions = {...}` / `action_map = {...}` 字面量的写法。
  若某 skill 改用其他方式注册 action，会被判为"无法判定"而跳过 —— 这是有意的保守行为。
- 解释器一致性在本机当前未实际发作（两版本探测结果相同），
  属于预防性修复而非已观测故障。

## 相关

- [[docs/adr/ADR-061-context-header-outside-rolling-window|ADR-061]]：同一次审计中发现的
  另一处"校验逻辑存在但不起作用"（`validate_context` 无条件返回"验证通过"）
- [[GOVERNANCE|治理标准]]：质量门禁的 fail-closed 要求
