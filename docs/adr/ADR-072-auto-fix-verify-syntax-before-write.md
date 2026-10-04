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

## 需求 → 检查映射（收口复核重测）

自动审查指出: 本 ADR 的验证此前只跑过 pytest 汇总, 属**间接证据**。
已新增 `tests/test_write_path_exit_code_acceptance.py`, 全部经
``subprocess`` 调真实 CLI (``hooks_runner.py language-rules --path ... --fix``),
逐条需求重测。**缺陷来自规则本身, 无需任何注入**:

| 显式需求 | 对应用例 | 实测退出码 | 实测磁盘 |
| --- | --- | --- | --- |
| 写盘前校验语法, 不通过则整体回退 | `test_bad_regex_rule_refuses_write_and_exits_nonzero` | 1 | md5 `80c6a37c8992`→`80c6a37c8992` 不变 |
| 拒绝时不声称已修复 | 同上 | 1 | 汇总 `0 auto-fixed, 1 manual fixes needed`（而非 `1 auto-fixed`） |
| 退出码只对 FAILED_WRITE_RULE_IDS 非零 | 同上 | 1 | `[syntax-check-rejected]` + `[MANUAL FIX REQUIRED]` |
| flag-only 规则**不得**弄红退出码（对照组） | `test_flag_only_rule_does_not_redden_exit_code` | 0 | md5 `b779c4bd8945` 不变 |
| 合法修复仍生效（对照组） | `test_valid_fix_still_applies` | 0 | md5 `b692c606aad9`→`cfbd246b85cb`, 可 `compile` |

变异验证（经 pytest 路径）: 短路 `_write_if_changed` 的兜底 → **恰好 1 条**
坏正则用例转红（磁盘确实被改坏、汇总退回 `1 auto-fixed`、退出码变 0），
另 7 条（含全部对照组）保持绿。回退 ADR-071 那三行 → 本组 3 条全绿，
证明两组变异互不串扰。

注：本组的 `FixEngine` 与 `fix_applier` 两处仍由
`test_fix_engine_write_verification.py` / `test_fix_applier_write_verification.py`
直接调用验证返回值与磁盘字节。

### 收口复核更正：两处先前记为“无生产调用方”，其中一处是错的

自动审查追问这两处的验证是否走过真实路径。重测时发现 ADR 与源码注释
都有一处**事实错误**：

| 位置 | 先前记录 | 实测 |
| --- | --- | --- |
| `FixEngine` | 无生产调用方 | **属实**（全仓除 `tools/fix_engine/` 外零引用） |
| `fix_applier` | 无生产调用方 | **错误** —— 有两个生产调用方 |

`fix_applier.apply_fixes` 的真实调用方：

- `tools/scripts/rules_engine/validators/cli.py::_apply_auto_fix`
  → CLI `validate_language_rules.py --fix`（`--fix` 是 `--help` 里
  明确列出的正式 flag）；
- `tools/scripts/validate_language_rules.py::apply_fixes`（同名包装）。

已在 `fix_applier.py` 的 docstring 中更正该错误陈述。

重测观测到的**两处行为**（直接调用，真实磁盘字节）：

| 场景 | 返回 | 磁盘 |
| --- | --- | --- |
| `FixEngine` 缺陷样本 | `success=False`、`syntax_violation=True`、`fixes_applied=0` | md5 `80c6a37c8992` 不变 |
| `FixEngine` 合法对照 | `success=True`、`fixes_applied=1` | `b692c606aad9`→`87a2c3cd24f5`，可解析 |
| `fix_applier` 字面量坏替换 | `[syntax-check-rejected]` + `[MANUAL FIX REQUIRED]` | md5 `26149c8ef04a` 不变 |
| `fix_applier` 字面量合法对照 | `[probe]`，`subprocess.run('ls')` | `b692c606aad9`→`9697baea9bdc`，可解析 |
| `fix_applier` sed 风格对照 | `[probe]`，`value = 2` | 已改，可解析 |

注意 ADR 早先记录的 `FixEngine` 合法对照 md5 尾号是 `5956eac524dd`，
本次实测为 `87a2c3cd24f5` —— 差异源于 `fix_file` 的默认参数组合
（本次显式传 `language="python"`）。属记录陈旧，非行为异常。

### 附带发现：`--fix` 是**死参数**，且被两层更深的原因遮蔽（未修，仅记录）

第一层：`validators/cli.py` 里 `args.fix` 的引用数为 **0**：

```
$ grep -c "args\.fix" tools/scripts/rules_engine/validators/cli.py
0
$ grep -n "args\.dry_run" tools/scripts/rules_engine/validators/cli.py
527:    fix_exit = _handle_auto_fix(results, args.dry_run)
```

即 `--fix` 被 argparse 解析、被 `--help` 列为正式选项，却从未被读取。
`git log -S` 显示 `--fix` 与该行**同属一个压缩提交** `f1d01d5`，
且 `args.fix` 从未被引用过 —— 这是**出生即死**，不是回归。

第二层（遮蔽了第一层）：即使把它接上，也**依然不会写盘**。实测
（`validate_language_rules.py <dir> --lang python --fix`）：

| 调用 | 退出码 | 文件被改 | 输出 |
| --- | --- | --- | --- |
| `--fix` | 1 | 否 | 无 Fixed/Would fix 行 |
| `--fix --dry-run` | 1 | 否 | 同上 |
| `--dry-run` | 1 | 否 | 同上 |
| 无参数 | 1 | 否 | 同上 |

即便临时接上 `args.dry_run or not args.fix`，四行结果**逐字相同**。

根因：`_apply_auto_fix` 只对带 ``fix_replacement`` 的 issue 调
`apply_fixes`，而 `validators/pipeline.py:347` 只在
``rule_def["fix_replacement"]`` 存在时才赋值。全仓 yml 中**仅
`ai-dev-framework/common/security.yml` 带该字段**；而该 CLI 对目录调用时
走 `_load_custom_rules` → `load_custom_rules(project_dir)`，实际加载的是
**`.ai-rules/`** 下的规则集，其中无一条带 `fix_replacement` ——
故 `apply_fixes` 合理地返回 0 条。CLI 确实**找到了**问题（输出里有
`py-bare-except` 等），只是没有可应用的替换串。

结论：修 `--fix` 需要**同时**解决两件事 —— 接上参数，且让规则集携带
`fix_replacement`。后者涉及规则语义（`SEC001` 等规则的替换文本该是
什么），ADR-072 末尾已明确把“改正则本身”列为需另行评估的事项。

**未修的理由**：这是**双重行为变更**（CLI 语义 + 规则数据），风险面
远大于 ADR-072 的写盘兜底；且当前行为是“只报告不写盘”，属保守失败，
不造成代码损坏。此处仅如实记录，并加回归用例锁死当前事实，避免下一个人
依据陈旧注释去验证一条**双重不可达**的写盘路径。

回归用例：`tests/test_write_path_fallback_contracts.py::
TestValidatorsCliFixFlagIsDead`。实测变异（每次恰 1 条转红，健康对照不受
影响）：

| 变异 | 预期 | 实测 |
| --- | --- | --- |
| 给 `.ai-rules/orph.yml` 加 `fix_replacement` | 第二层断言转红 | 1 failed / 9 passed ✓ |
| 把 pipeline 守卫 `if "fix_replacement" in rule_def` 改写 | 第一条断言转红 | 1 failed / 9 passed ✓ |

（此处也有个自我更正：最初我用 `security.yml` 做的变异是**无效变异** ——
它本就在断言的白名单内，测试理应全绿。“变异后全绿”不等于“测试没作用”，
关键要问**变的是不是断言真正覆盖的东西**。）

### 附带发现：早期一版结论本身也是错的（自我更正）

本节初稿实测时**漏了** `--lang`，CLI 在参数校验阶段就
`Error: Use --lang or --auto-detect for directories.` 退出 1，于是我
误记为“该 CLI 等价于永远 dry-run”。补上 `--lang python` 后才看到
它**确实找到了问题**，只是没有可应用的替换串。前一结论作废，
以本节上表为准。

这条本身就是本轮方法学的注脚：**观测被参数校验挡住时，容易把
“没走到那段代码”误判成“那段代码的行为”**。

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

## 第四条写盘路径：`fix_applier.apply_fixes`

收口复核时按 ADR-072 的根因（“正则改写代码这一手法缺少与规则无关的
写盘兜底”）重新扫了全仓写盘点，发现 `tools/scripts/fix_applier.py`
的 `apply_fixes` 是**完全没加兜底**的第四条路径，且**能真实写坏代码**。

取证（实测，非推断）：`_apply_literal_replacement` 取 `issue.message`
最后一个冒号后的文本做替换，`fix_replacement` 本身坏掉时直接把文件改坏，
而函数仍返回 1 个 `FixResult`——即**声称修复成功**：

| 样本 | 输入 → 磁盘 | 解析 | 返回 |
| --- | --- | --- | --- |
| 未闭合括号 | `y = 2` → `y = (2` | `SyntaxError: '(' was never closed` | 1 个 FixResult |
| 函数头失效 | `def f():` → `def f(def f():` | `SyntaxError: invalid syntax` | 1 个 FixResult |
| 缩进失效 | `if True:` → `if Trueif True:` | `SyntaxError: invalid syntax` | 1 个 FixResult |
| 健康对照 | `os.system('ls')` → `subprocess.run(...)` | 仍可解析 | 1 个 FixResult |

同 ADR-072 对 `FixEngine` 的处理：它**无生产调用方**（实测：全仓除
`build/lib/` 构建产物与 28 处测试引用外零引用），但那个理由已被明确
否决过，故同批补上。修法复用 `auto_fix._verify_syntax`，不另写一份。

> **收口复核更正**：本节初稿把 `fix_applier` 也记为“无生产调用方”，
> 那是**错的** —— 它有两个生产调用方，详见上方「收口复核更正」。
> `FixEngine` 的“无调用方”判断经本轮实测**仍然属实**。

新增 `tests/test_fix_applier_write_verification.py`，含两条替换分支
（字面量与 sed 风格）的对照组，防止只测了一半：

| 场景 | 观察值 |
| --- | --- |
| 缺陷样本 | 返回 `syntax-check-rejected` + `[MANUAL FIX REQUIRED]`，磁盘 md5 `26149c8ef04a` → `26149c8ef04a`（逐字节不变） |
| 合法样本（对照） | 返回 `rule_id=probe`，磁盘 `44263951f17c` → `92a21a095da8`，修复后仍可 `compile` |
| sed 分支（对照） | 磁盘 `1a3342c47fa5` → `f4b6a872ee56`，仍可 `compile` |
| `dry_run` | 磁盘不变且不报拒绝 |

变异（短路 `if checked and violation`）→ `1 failed`，输出直接重现损坏
形态（磁盘 `26149c8ef04a` → `461b6f8e0562`，返回 `probe` / `y = (2`），
三个对照组保持绿。还原后 `4 passed`。

### 附带修正：又一处一直在验证假象的存量夹具

`tests/test_language_rules_v2.py::TestAutoFix` 的两个用例用顶格裸
`except:` 作夹具——**这本身就不是合法 Python**。旧实现无条件写盘，
它们一直是绿的，实际在验证“把一份非法文件改成另一份非法文件”。加上
兜底后转红，这正是兜底生效的证据。已把夹具改为合法的 `try/except`
结构，而非放宽兜底去迁就非法输入。

这已是**第三处**同型存量夹具（另两处见本 ADR「附带修正」与 ADR-072
初版记录），说明“用非法输入当夹具 + 无条件写盘”是一个反复出现的
模式，而非孤立事故。

## 相关

- ADR-070：写盘前必须校验修复结果的语法
- ADR-071：目录模式存在文件被拒时必须以非零退出
