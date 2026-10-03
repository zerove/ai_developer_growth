# ADR-071: 目录模式存在文件被拒时必须以非零退出

## 状态

接受

## 日期

2026-10-03

## 影响组件

- `tools/scripts/hooks/phase_runner.py`（`_run_ast_fix` 目录分支）
- `tests/test_ast_fixer_write_verification.py`（`TestDirectoryExitCodeOnRejection`）
- `docs/api/cli.md`

## 背景

ADR-070 修好了"写盘前校验语法"，并在**输出**层面锁死了失败呈现：
汇总行必须打印 `❌ Syntax check failed`，且该行优先于
`✅ Fixes applied`。回归测试也覆盖了目录模式——但只断言了 stdout，
**没有一条断言退出码**。

真实 CLI 实测（Phase 46 收口复核，经子进程注入真实
`IndentationError`，非伪造判定）暴露了漏网之处：

```
=== 目录模式 + 真实破坏 ===
  Total fixes found: 4 (2 auto-safe)
  Fixes applied: 0
  ❌ 2 file(s) rejected: fixes would break syntax (ADR-070)
      Files left unchanged. Fix the reported syntax error manually.
  ❌ Syntax check failed — see messages above
目录模式退出码=0
```

输出明明白白说失败，进程却以 0 退出。`phase_runner.py` 的目录分支
无条件 `return 0`。

## 问题性质

这不是"提示不够醒目"，而是一盏**脚本唯一真正读的那盏绿灯**：

- CI 判定、`pre-commit` 拦截、任何 `if ! <cmd>; then` 读的都是退出码；
- stdout 是给人看的，退出码是给机器判的；
- ADR-070 修的正是"报告成功而磁盘未改"，而目录模式只是把同一盏
  假绿灯从**文本挪到了进程状态**上——换了个位置，没换掉。

单文件路径没这个问题：它按 `auto_safe` 项数返回，被拒时该项数
恰好 ≥1。ADR-070 当时只在单文件分支加了 `violations` 参与返回值，
目录分支漏掉了同一处——**同一修复里的一半**。

`git log -L` 确认该 `return 0` 自 ADR-068（`51e918e`）起就在，
即这是存量缺陷，ADR-070 未覆盖到。

## 决策

目录分支在**存在被拒文件**时返回 `1`，否则保持 `0`。

不改为 0/1 语义的原因：单文件退出码是"auto-safe 项数"这一
`docs/api/cli.md` 写明的既有契约，与通过/失败无关；目录路径返回 0
本就只表示"扫完了"。因此只在"有失败"这一档上从"总是 0"改为
"有失败才非零"，不触碰任何既有约定，也不会让现有 CI 阈值失准。

## 验证

真实 CLI（子进程 + `sys.argv`，全链路未经简化），注入的是劫持
`_apply_fix` 的 sitecustomize，使其产出**真的非法** Python——
不是伪造报告字段：

| 场景 | 退出码 | 磁盘 |
| --- | --- | --- |
| 目录：1 文件被拒 | 0 → **1** | 逐字节不变 |
| 目录：部分成功部分被拒 | 0 → **1** | 被拒者不变，成功者已改 |
| 目录：仅合法修复 | 0（不变） | 正常改写，仍可解析 |
| 单文件：被拒 | 1（不变） | 逐字节不变 |

对照组确认兜底真实生效：移除 `_verify_syntax` 后，同一真实 CLI
确实把文件写坏（md5 变化），并非输出文案在表演。

变异验证：仅回退本次那三行，恰好 2 条目录用例变红
（`test_directory_exit_code_nonzero_when_file_rejected`、
`..._on_partial_success`），两个对照组用例保持绿。

## 后果

- `ast-fix --path <目录>` 在有文件被拒时会真正阻断 CI/pre-commit。
- 既有调用方若依赖目录模式恒为 0，会在语法拒绝场景下改为非零——
  这正是本 ADR 的意图，且该场景此前是静默假绿。

## 被否决的方案

1. **一并把单文件退出码改成 0/1**：会破坏 `docs/api/cli.md` 写明的
   "auto-safe 项数"契约，令既有 CI 阈值失准。单文件被拒时该项数
   本就 ≥1，已能表达失败，无需改动。
2. **只在输出里加更多警告**：退出码仍为 0，机器依旧判绿。问题出在
   进程状态，加文本不解决问题。
3. **让 `_print_directory_summary` 返回值并传递**：输出函数不该承担
   状态传递职责，计数与判定在 `_run_ast_fix` 里就地判断更直接。

## 相关

- ADR-070：写盘前必须校验修复结果的语法
- ADR-068：ast-fix 必须区分"发现"与"已应用"
- ADR-069：auto-fix 不得破坏语法
