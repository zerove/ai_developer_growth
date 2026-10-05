# ADR-077: "不写盘"与"提前退出"是两个语义，不得复用同一个布尔

## 状态

接受

## 日期

2026-10-05

## 影响组件

- `tools/scripts/rules_engine/validators/cli.py`（`_apply_auto_fix` / `_handle_auto_fix` / `main`）
- `tests/test_write_path_fallback_contracts.py`（新增 `TestNoFixFlagMustNotSkipOutputStages`，4 个用例）

## 背景

ADR-072 的配套修复把 `--fix` 从**死参数**接成真实开关：

```python
fix_exit = _handle_auto_fix(results, args.dry_run or not args.fix)
```

该修复本身正确且必要（原先只要有人给规则加上 `fix_replacement`，CLI 就会在
用户未传 `--fix` 时静默改写代码）。但它复用了一个**语义已经污染**的参数
`dry_run`，由此引出一个此前不存在的回归。

本次复盘审阅未提交改动时发现该问题。**注意这不是"测试没跑到"**：新加的
`TestFixFlagEndToEnd` 三个用例全部通过，缺陷依然存在 —— 它们只断言磁盘
有无被改写，而回归的表征是**输出被吞**。

## 缺陷

`_apply_auto_fix` 末尾有一个历史遗留的早退信号：

```python
if dry_run and not results:
    return -1          # Signal: return early
return 0
```

`_handle_auto_fix` 把它翻成退出码，`main` 再按"非 None 即退出"处理：

```python
fix_result = _apply_auto_fix(results, dry_run=dry_run)
if fix_result == -1:
    return 0           # main 在此直接 return
```

问题在于 `dry_run` 原本只被用来表示"**别写盘**"，而这个 `return -1`
让同一枚比特还额外控制了"**要不要跳过后续输出阶段**"。两个毫不相关的
语义被塞进了同一个参数。

ADR-072 之前，这条早退路径几乎不可达 —— 不传 `--dry-run` 时 `dry_run`
恒为 `False`。ADR-072 之后，**不传 `--fix` 也必须走 `dry_run`**，
于是只要 `results` 为空，这条路径就必然被触发。

### 实测（修复前）

`--incremental` 且文件未变化时 `results` 为空，正是最容易触发的场景：

| 调用 | 调用点返回 | 实际输出 |
| --- | --- | --- |
| `--incremental --json`（不传 `--fix`） | `0` → main 提前 return | 45 字符，**JSON 被整段吞掉** |
| `--incremental --json --fix` | `None` → 继续 | 195 字符，完整 JSON |

修复后：

| 调用 | 调用点返回 | 实际输出 |
| --- | --- | --- |
| `--incremental --json`（不传 `--fix`） | `None` → 继续 | 195 字符，完整 JSON |
| `--incremental --json --fix` | `None` → 继续 | 195 字符，完整 JSON |

## 严重度：第七类"假绿灯"

本仓库此前已记录六类"报告与真实脱节"（ADR-057 CI 心跳、ADR-061 校验
fail-open、ADR-064 检查没跑却报通过、ADR-065 检查了 0 个却报通过、
ADR-066 声称已修改却没修改、ADR-068 部分成功却报绿）。本条是第七类，
且形态更隐蔽：

- **退出码是 0**，任何以退出码为准的门禁都会判定通过；
- `--health-score` / `--json` 的输出变成空字符串，依赖 JSON 的下游
  调用方拿到的是空数据而非报错；
- 相比之下，ADR-066 至少还会在磁盘上留下痕迹。

## 决策

把"修不修"与"走不走"彻底分开：

1. **移除 `-1` 早退信号**。`_apply_auto_fix` 对空结果返回 `0`
   ——无结果时本就无事可做，也没有理由替调用方决定"到此为止"。
2. **`_handle_auto_fix` 恒返回 `None`**。auto-fix 阶段只负责写盘与否，
   不再越权决定流程是否继续。
3. **`--fix` gating 保持不变**。它是对的，问题出在被复用的参数上。

原 `-1` 唯一的实际价值是"没有可看的文件就别刷屏"，但那属于**输出策略**，
应由 `_handle_output` / `print_results` 决定，不由 auto-fix 阶段代劳。

## 验证

新增 `TestNoFixFlagMustNotSkipOutputStages`（4 个用例）：

| 用例 | 断言落点 |
| --- | --- |
| `test_json_output_survives_missing_fix_flag` | 真实子进程，stdout 含 `"results"` |
| `test_health_score_survives_missing_fix_flag` | 真实子进程，stdout 含 `Health Score` |
| `test_output_is_identical_with_and_without_fix_flag` | 两种调用 stdout **逐字节相同** |
| `test_empty_results_no_longer_triggers_early_exit` | 直接断言 `_apply_auto_fix` / `_handle_auto_fix` 返回值 |

### 变异验证

| 变异 | 结果 |
| --- | --- |
| 基线（修复版） | 20 passed |
| 变异 A：只把 `return 0` 改回 `return -1` | **1 failed** / 19 passed |
| 变异 B：还原**完整缺陷形态**（早退信号 + `_handle_auto_fix` 翻写） | **4 failed** / 16 passed |

变异 A 只让 1 项转红，说明**端到端断言对部分变异不敏感** —— 只有
返回值契约那条能立刻抓到。变异 B 还原完整形态后 3 项端到端断言全部转红，
证明它们确实覆盖了真实用户路径。两种变异下健康对照均不受影响。

本轮变异过程中出了一次**假阴性**：第一次注入变异时用了锚点脚本而非
`edit`，锚点匹配 0 次导致变异**根本没写入**，测试"全绿"。这与 ADR-072
记录的 `git stash` 静默失效是同一类陷阱 —— **必须先确认变异标记真的
出现在源码里，再看测试结果**。

## 教训

- **修好一个真实缺陷时，要问"这条新路径经过了哪些既有分支"**。ADR-072
  让某条分支的可达性从"几乎不可能"变成"必然触发"，那条分支上残留的
  历史假设就会立刻变成缺陷。
- **一个布尔参数承载多个语义时，加固它反而会引爆旧债**。正确做法是
  在接入前就拆开语义，而不是让新调用方去适配旧的歧义。
- **回归测试要断言"用户可见的行为"，不是"被改的那个字节"**。本次三个
  端到端用例全绿却漏掉了真缺陷，正是因为它们只盯磁盘。

## 相关

- ADR-072 —— `--fix` 死参数修复（本次是其连带缺陷）
- ADR-064 / ADR-065 / ADR-066 / ADR-068 —— 前六类假绿灯
