# ADR-079: 可直接执行的脚本必须自行引导仓库根到 sys.path

## 状态

接受

## 日期

2026-10-10

## 影响组件

- `tools/scripts/hooks_runner.py`
- `tests/test_ast_fix_cli_applied_reporting.py`
- 同类缺陷脚本 15 个（见「遗留限制」）

## 背景

清理无用文件时对 `tools/scripts/hooks_runner.py` 做删除候选筛查，
`python tools/scripts/hooks_runner.py --help` 直接崩：

```
ModuleNotFoundError: No module named 'tools'
  File "tools/scripts/hooks_runner.py", line 41, in <module>
    from tools.scripts.hooks.basic_checks import (...)
```

### 根因

该文件用**包绝对导入**（`from tools.scripts...`）开头，但
`pre-commit` 钩子与多个测试都以**脚本路径**方式调用它：

- `.pre-commit-config.yaml:121` `entry: python tools/scripts/hooks_runner.py ...`
- `tests/test_ast_fix_cli_applied_reporting.py:43` 子进程跑真实 CLI

以脚本路径执行时 `sys.path[0]` 是 `tools/scripts/`（脚本所在目录），
**仓库根不在其中**，于是包绝对导入全部失败。以
`python -m tools.scripts.hooks_runner` 执行则正常（`-m` 由包上下文解析
`sys.path`，仓库根本来就在）。

也就是说这个文件"两种写法只支持一种"，而门禁恰好用的是坏的那种。

### 为什么此前没被发现

`pytest.ini:2-3` 的 `testpaths = tests` 只收集 `tests/`，而全量门禁
用的是 `python -m pytest`（`-m` 形式对被测代码的导入方式没有影响，
但被测代码**自己**的直接执行路径未被门禁覆盖）。该文件的历史
最后修改在 2026-10-03（`29592bc`），缺陷随那次拆分
（`_CHECK_PHASES` 阶段函数改为按名称字符串运行时解析）进入。

## 决策

在 `tools/scripts/hooks_runner.py` 顶部、包绝对导入**之前**插入仓库根：

```python
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
```

并给受影响的 11 处模块级导入补 `# noqa: E402`
（导入不在文件顶部，因 `sys.path` 引导必须先行 —— 这是**刻意的**顺序，
不是疏忽）。

采用既有先例而非新发明：`.jcode/scripts/_common.py:17-19`
与 `tools/scripts/jcode_ai_native_workflow.py:21-23` 都是同一写法。

## 后果

### 正面

- `tests/test_ast_fix_cli_applied_reporting.py` 7 个测试由红转绿。
  该组测试锁的正是 ADR-068「CLI 不得谎报 Fixes applied」的回归，
  此前因导入崩溃而**整组失效** —— 门禁上的假绿灯。
- `python tools/scripts/hooks_runner.py` 与 `python -m` 两种写法等价，
  消除"只有一种能用"的隐式约束。

### 负面 / 代价

- 补 11 处 `# noqa: E402` 增加噪音。换来的是 `ruff check` 保持零错误 ——
  项目基线（`.jcode/baseline.json`）是棘轮式，不允许新增豁免。

## 遗留限制

**同类缺陷仍存在于 15 个脚本**，本次未一并修复（超出清理任务范围）。
逐个 `python <脚本> --help` 探测可复现清单：

```
tools/scripts/ai_context_manager.py        tools/scripts/rule_registry.py
tools/scripts/ai_quality_gate.py           tools/scripts/rule_visualize.py
tools/scripts/detect_language.py           tools/scripts/update_ai_tool_matrix.py
tools/scripts/generate_fixes.py            tools/scripts/validate_language_rules.py
tools/scripts/git_diff_incremental.py      tools/scripts/validate_rule_tests.py
tools/scripts/jcode_cli.py
tools/scripts/perf_benchmark.py
tools/scripts/rule_author.py
tools/scripts/rule_editor.py
tools/scripts/rule_marketplace.py
```

其中 `validate_language_rules.py` 已被测试以脚本路径调用，导致
`tests/test_write_path_fallback_contracts.py` 等 16 个测试失败
（该组测试锁的是 ADR-071/ADR-077 的写盘路径契约）。已确认这 16 个
失败在纯净 HEAD 上同样存在，非本次改动引入。

**建议后续**：要么批量套用本 ADR 的引导，要么让门禁只走 `python -m`
一种形式。后者更彻底 —— 消除"可被直接执行"这个隐式契约。
