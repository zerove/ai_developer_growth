# ADR-066: ASTFixer 报告的修复必须真正落盘

## 状态

接受

## 日期

2026-10-03

## 上下文

Phase 40 收口时把 `ast_fixer` 记为"范围较窄的可观测性缺陷"——
单文件路径不打印修复明细。Phase 42 按遗留清单逐项复核，
准备修那个"输出缺失"时，发现了一个**严重得多**的问题。

## 决策

1. `ASTFixer.fix_file` 在非 dry-run 时必须把 `fixed_content` 写回文件；
   写回失败必须让调用方知晓，不得静默返回"已修复"报告。
2. `FixReport` 新增 `applied_fixes` 字段，区分"发现的可修复项"
   与"真正改变了文本的项"。
3. 单文件路径的 `verbose` 显式设为 `True`。

## 实测证据

### 一、缺陷：声称已修复，实际未改

探针含裸 `except`（`fix_file` 确实识别出 2 个可修复项）：

```
fix_file 返回: FixReport
total_fixes = 2
fixes 明细: rule='fix-empty-except' line=9 auto_safe=True
            rule='fix-bare-except'  line=8 auto_safe=True
文件是否被修改: False
裸 except 修复前后计数: 1 -> 1
```

非 dry-run 运行后裸 `except` 仍在磁盘上。真实 CLI 表现：

```
  AST AUTO-FIX
============================================================
EXITCODE: 2
```

退出码 2 来自 `total_fixes`，会让用户认为"改了 2 处"。
目录路径更严重——`_print_directory_summary` 会打印
`✅ Fixes applied`。**报告与磁盘状态完全脱节。**

### 二、根因

`fix_file`（`ast_fixer.py:101-106` 原实现）：

```python
fixed_content = content
if not dry_run:
    for fix in fixes:
        if fix.auto_safe:
            fixed_content = self._apply_fix(fixed_content, fix)
# ← 之后再无任何写回操作
return FixReport(..., total_fixes=len(fixes), ...)
```

`fixed_content` 只进了返回值，**从未写入 `filepath`**。
`_apply_fix` 本身是正确的——实测 `fixed_content` 内
裸 `except` 计数为 0，缺的只是一次写回。

这是本项目发现的**第三类假绿灯**：
ADR-064 是"检查没跑却报通过"，ADR-065 是"检查了 0 个却报通过"，
本 ADR 是"**声称已修改却没修改**"。三者都属"报告状态与真实状态脱节"。

### 三、修复后

```
[1] 非 dry-run
    total_fixes = 2 | applied_fixes = 2
    磁盘裸 except 计数: 0
    磁盘 == fixed_content: True
[2] dry-run
    文件未被修改: True
    applied_fixes = 0
[3] 幂等性（对已修复文件再跑）
    total_fixes = 0 | applied_fixes = 0
```

### 四、变异验证

两处变异（移除写回块 + 单文件恢复 `verbose=False`），
先确认变异实际生效（脚本内断言命中），再运行测试：

```
5 failed, 5 passed
```

失败的 5 个全部对应两个缺陷：
- `test_non_dry_run_actually_modifies_file`
- `test_disk_matches_fixed_content`
- `test_rerun_on_fixed_file_finds_nothing`
- `test_cli_single_file_prints_fix_details`
- `test_cli_single_file_really_changes_file`

通过的 5 个是对照组（dry-run 不写、干净文件不动等）。

## 关键发现：断言必须对准真实的输出路径

新测试首版断言单文件 CLI 输出包含 `✅ Fixes applied`，结果 **2 个用例失败**。
排查后发现该字符串只存在于 `_print_directory_summary`
（`phase_runner.py:340`），而**单文件路径根本不经过它**。
断言写错了对象，不是实现有问题。已改为断言
`format_fix_report` 的输出体（`fix-bare-except` / `Total fixes: 2`）。

这与 Phase 40 记录的"给函数内 `from`-import 的局部名字赋值"同源：
**在没读代码的情况下猜测某个字符串出现在哪条路径上。**

## 关键发现：`total_fixes` 不足以描述结果

`total_fixes` 统计的是"发现的可修复项"，不保证每项都真正改动了文本——
`_apply_fix` 在行号越界时会原样返回内容（`ast_fixer.py:332-333`）。
修复前这两者无法区分，报告因此可以**夸大**自己的成果。
新增 `applied_fixes` 后，报告能自证"发现 N 项、实际生效 M 项"，
`applied_fixes != total_fixes` 就是可观测的降级信号。

## 备选方案

- **在 CLI 层写回**：治标。`ASTFixer` 的其他调用方仍会踩坑，
  且 `FixReport.fixed_content` 已经承诺了修复后内容，不落盘就是撒谎。
- **让 `fix_file` 直接改文件并返回计数**：会破坏现有返回 `FixReport`
  的契约，影响面更大。选择保留返回值 + 落盘。

## 影响

- **`ast-fix` 非 dry-run 现在真的会改文件**。这是它一直被宣称的
  行为，但此前从未发生。若有脚本依赖"运行了但没变"的现状，
  会开始看到真实改动 —— 这正是期望的修复。
- 写回失败（`OSError`）时 `fix_file` 返回 `None`，调用方按
  "无法解析"处理并提示，不会误报成功。
- dry-run 行为不变，仍不触碰文件。

## 落盘修复暴露的新风险（未处理，需决策）

修复前 `fix_file` 从不写盘，因此下列问题**从未有机会显现**。
写回生效后，它们变得可达：

实测 `ast-fix --path tools/scripts --dry-run` 得到
**204 处 auto-safe 修复**，且抽样查看后**全部**是
`fix-empty-except`，其替换内容为：

```python
pass  →  pass  # TODO: Handle this exception
```

该规则在 `_fix_bare_except_pass` 中被标为 `auto_safe=True`，
但插入 `# TODO` 注释并非"安全修复"——它降低代码质量而非提升，
且 204 处批量注入会污染整个代码库。

对比 `fix-bare-except`（`except:` → `except Exception:`，
置信度 0.95）是真正的语义安全改写。把二者同标 `auto_safe=True`
混淆了"语法安全"与"质量有益"。

**本 ADR 未处理此项**：修改规则默认值会改变工具行为，
超出"让报告与磁盘一致"的范围，且 204 处批量改写属于
需要用户确认的改动。已记录为待决策项。

## 相关 ADR

- ADR-065：路径不存在必须显式失败（同源系列的另一类假绿灯）
- ADR-064：语义检查降级必须可见
