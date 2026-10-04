# ADR-072: auto-fix 写盘前必须校验语法，且拒绝时不得声称已修复

## 状态

接受

## 日期

2026-10-03

## 影响组件

- `tools/scripts/rules_engine/auto_fix.py`（`_verify_syntax`、`_write_if_changed`、`apply_fixes`、`FAILED_WRITE_RULE_IDS`）
- `tools/scripts/hooks_runner.py`（`_handle_language_rules`）
- `tests/test_auto_fix_write_verification.py`
- `tests/test_auto_fix.py`

## 背景

ADR-070 给 `ASTFixer.fix_file` 加了写盘前语法自检，并明确留下
一条遗留限制：

> **只覆盖 `ASTFixer.fix_file`**：`tools/fix_engine/FixEngine.fix_file`
> 是另一条独立写盘路径，未加兜底。

本阶段按图索骥地查了这条限制，结果比预想的严重：**不止一条路径
没兜底，而且其中一条在真实 CLI 上每天都在用。**

### 缺陷 1：`FixEngine`（无生产调用方）

`tools/fix_engine/__init__.py` 第 158 行无条件 `write_text`。
实测（无需任何注入）：

```
输入: import os
      cmd = os.system(f"ls {d()}")
输出: import subprocess
      cmd = subprocess.run(f"ls {d(, shell=True, check=True)}")
      → SyntaxError: f-string: expecting '=', or '!', or ':', or '}'
```

但全仓检索确认：`FixEngine` **没有任何生产调用方**，仅
`tests/test_adg_new_modules.py` 使用。其伤害是潜在的，不是现实的。

### 缺陷 2：`auto_fix.apply_fixes`（有生产调用方，且是 CLI 子命令）

`tools/scripts/rules_engine/auto_fix.py` 的 `_write_if_changed`
同样无条件写盘，且**内嵌了一份与 `fixes.yml` 同源的坏正则**。
真实 CLI 实测：

```bash
$ hooks_runner.py language-rules --path lrf --fix
📄 lrf/s.py
  🔧 Line 2: [py-os-system] Replace os.system() with subprocess.run()
     Original: os.system(get_cmd()
     Fixed:    subprocess.run(get_cmd(, shell=True, check=True)

Summary: 1 issues found, 1 auto-fixed, 0 manual fixes needed
$ echo $?
0
```

磁盘上的文件已无法解析，CLI 却报告 **1 auto-fixed** 且退出 **0**。

### 根因

两处同源：正则里的 `[^)]+` 捕获组遇到嵌套括号就在第一个 `)`
处截断，把参数列表从中间劈开。这不是"某条规则写错了"，而是
**正则改写代码这一手法缺少与规则无关的写盘兜底**——与 ADR-070
诊断出的完全一致。

ADR-070 的兜底写在 `ast_fixer` 内部，没有覆盖到这条路径。当时
把"未加兜底"记为遗留限制是对的，但只记住了 `FixEngine` 一处，
漏掉了真正在用的 `auto_fix`。

## 问题性质

比 ADR-070 更糟的一档：

| | ADR-070（ast-fix） | 本 ADR（auto-fix） |
| --- | --- | --- |
| 输出 | 报 `❌ Syntax check failed` | 报 **`1 auto-fixed`** |
| 退出码 | 1 | **0** |
| 磁盘 | 未改 | **已改坏** |

汇总**主动声称成功**，这是"声称已修复"而非"未报告"。

## 决策

1. `auto_fix._write_if_changed` 写盘前必须通过语法自检；不通过则
   **整体回退**，一个字节都不写。
2. 拒绝时**丢弃**此前累积的 auto-fix 结果，只保留一条
   `syntax-check-rejected`，且其 `fixed` 字段必须取
   `[MANUAL FIX REQUIRED]` 哨兵。
3. 写盘 `OSError` 同样成为一条 `write-failed` 结果，不得静默。
4. CLI 存在上述任一结果时退出非零。
5. 自检实现**复用** `ASTFixer._verify_syntax`，不另写一份。

### 为何第 2 条的哨兵值是关键细节

`_summarize` 与 `_format_text` 都以 `r.fixed != "[MANUAL FIX REQUIRED]"`
判定"是否已自动修复"。若拒绝记录的 `fixed` 留空字符串，它会被
**计入 `auto-fixed`**——兜底挡住了写盘，汇总却仍报告成功，等于
原地绕回假绿灯。这一点由变异 C 实测确认（见下）。

### 为何第 4 条不能扩大化

退出码**只**对 `FAILED_WRITE_RULE_IDS`（`syntax-check-rejected`
与 `write-failed`）非零，**刻意不含** flag-only 规则的
`MANUAL FIX REQUIRED`。后者（如 `py-star-import`）本就是"建议
人工处理"的正常产物；若一并弄红退出码，既有 CI 会长期红，
等于用一个假绿灯换一个真误报。

该 ID 集合定义在**生产方** `auto_fix.py`，由 CLI import，
避免两处字面量各自漂移。

## 验证

真实 CLI（`language-rules --path <dir> --fix`，全链路未简化），
缺陷来自规则本身，**无需任何注入**：

| 场景 | 退出码 | 磁盘 | 汇总 |
| --- | --- | --- | --- |
| 正则改坏语法 | 0 → **1** | 逐字节不变 | `1 auto-fixed` → `0 auto-fixed, 1 manual fixes needed` |
| flag-only 规则 | 0（不变） | 不变 | `MANUAL FIX REQUIRED`，退出仍 0 |
| 合法修复 | 0（不变） | 正常改写，仍可解析 | `1 auto-fixed` |

三处变异分别确认：

- **A 短路语法自检** → **4 failed**，失败输出里可见磁盘被改成
  `subprocess.run(get_cmd(, shell=True, check=True))`；
- **B 退出码不再反映拒绝** → **1 failed**（仅退出码那条）；
- **C 拒绝项 `fixed` 留空** → **2 failed**，实测汇总退化回
  `Summary: 1 issues found, 1 auto-fixed, 0 manual fixes needed`。

## 附带修正：一个一直在验证假象的存量用例

`tests/test_auto_fix.py::test_fixes_python_files` 的夹具是顶层
`except:\n    pass`——**这本身就不是合法 Python**（`except` 必须
跟在 `try` 之后）。旧实现无条件写盘，该用例一直是绿的，实际
在验证"把一份非法文件改成另一份非法文件"。

加上兜底后该用例转红，这正是兜底生效的证据。已把夹具改为合法
的 `try/except` 结构，而非放宽兜底去迁就非法夹具。

## 后果

- `language-rules --fix` 从此不会写坏文件，也不会在写坏时声称成功。
- 依赖该子命令返回 0 的流程，在发生语法拒绝时会转为非零——这正是
  本 ADR 的意图。

## 关于 `FixEngine`

本 ADR 起初把 `FixEngine` 记作遗留项，理由是它无生产调用方。
写完后复核认为该理由不成立：**它读的是与 `auto_fix` 同源的
`fixes.yml`，接入生产即会复现本 ADR 的形态**，而修复只需复用
已导出的 `_verify_syntax`。留一个已知会写坏代码的入口而不修，
代价（一次静默的代码损坏）远大于改动本身，故同批补上：

- 修复结果不可解析时返回 `success=False`、带
  `syntax_violation=True`，磁盘逐字节不变；
- 合法样本照常修复（对照组锁定，防止退化成"永不修复"）。

`fixes.yml` 里的坏正则本身**未改**——那是行为变更，需另行评估
`SEC001`/`SEC002` 等规则的替换语义，不能夹在兜底修复里悄悄改。

### 复核补记（Phase 收口）

初版验证只经 `tests/test_adg_new_modules.py` 间接触及 `FixEngine`，
**从未直接调用并观察返回字典与磁盘字节**——那属于间接证据。
新增 `tests/test_fix_engine_write_verification.py` 直接调用并打印实况：

| 样本 | 观察值 |
| --- | --- |
| ADR-072 记录的缺陷样本 | `success=False`、`syntax_violation=True`、`fixes_applied=0`，磁盘 md5 `80c6a37c8992` → `80c6a37c8992`（逐字节不变） |
| 合法样本（对照） | `success=True`、`fixes_applied=1`，磁盘 `a8ff44f1a640` → `5956eac524dd`，修复后仍可 `compile` |
| 无可修复项样本 | `syntax_violation` 键**根本不出现**，证明兜底未无条件介入 |
| `dry_run=True` | 磁盘不变，且不报语法违规 |

变异（把 `if checked and violation` 短路为 `if False`）→ `1 failed`，
失败输出直接重现 ADR-072 记录的原始损坏形态：

```
磁盘 md5 80c6a37c8992 -> b759f683945d
磁盘内容='import subprocess\n\nimport os\ncmd = subprocess.run(f"ls {d(, shell=True, check=True)}")\n'
```

三个对照组在变异下**保持绿**，说明它们确实在测兜底开关而非侥幸通过。
还原后 `4 passed`。

## 相关

- ADR-070：写盘前必须校验修复结果的语法
- ADR-071：目录模式存在文件被拒时必须以非零退出
