# ADR-068: ast-fix 报告必须区分"发现"与"已应用"

## 状态

接受

## 日期

2026-10-03

## 影响组件

- `tools/scripts/hooks/phase_runner.py`
- `docs/api/cli.md`

## 背景

ADR-067 把 `fix-empty-except` 降级为 `auto_safe=False`（只报告、不自动应用）。
降级本身经双向变异验证正确，但**紧接着用真实 CLI 复验时发现另一处缺陷**：

```
$ hooks_runner.py ast-fix --path <含 except-pass 的目录>
      Total fixes: 1
      ✅ Fixes applied
$ cat 探针文件      # 一个字节都没变
```

CLI 明确宣称已应用，磁盘却完全没动。

## 缺陷根因

`_fix_single_file` 只返回**一个**整数 `report.total_fixes`，
而这个数是**发现数**；`_print_directory_summary` 依此打印
`✅ Fixes applied`。ADR-066 引入 `applied_fixes` 正是为了区分
"发现了什么"和"实际改动了什么"，但**只改了 `FixReport`，没改 CLI 报告层**。

三种含义被压缩进同一个数：

| 语义 | 含义 | 何时不等于其他 |
| --- | --- | --- |
| `found` | 检出的可修复项 | 永远 >= 其余两者 |
| `auto_safe` | 其中可自动应用的 | report-only 规则不计入 |
| `applied` | 实际改写了文本的 | dry-run 恒为 0；`_apply_fix` 行号越界时也可能偏小 |

ADR-067 引入 report-only 规则，让这三者**第一次真的不相等**，
于是这个一直存在的缺陷被迫显形。

## 决策

1. 引入 `FileFixResult(NamedTuple)` 显式承载三个计数，
   取代原先的裸 `int` 返回值——让"可以不相等"这件事在类型上可见。
2. 汇总同时打印三项，并**按 `applied` 而非 `found` 选择结论行**：
   - `applied > 0` → `✅ Fixes applied: {applied}/{found}`
   - `applied == 0 且 found > 0` → `ℹ️ N review-only fix(es) reported, none applied`
   - `found == 0` → `✅ No fixes needed`
3. 单文件路径的退出码沿用 `docs/api/cli.md` 既有约定
   （= auto-safe 修复数），**不随本次改动变更**。

## 关键修正：退出码契约一度被误改

首版实现把单文件退出码从 `auto_safe` 改成了 `applied`，
理由是"退出码应当反映真实改动"。改完立刻有
`test_cli_dry_run_does_not_change_file` 失败。

该测试原本断言 `returncode == 2`，而该 fixture 实测
found=2 / auto_safe=1。旧实现返回 `total_fixes`（= 2），故断言通过；
按契约正确实现后应返回 `auto_safe`（= 1），断言随即失败。

复查 `docs/api/cli.md` 确认契约明文写着"单文件退出码 = auto-safe
修复数"，故退出码**必须**按 `auto_safe`。

这暴露了一个更普遍的问题：**断言里写死的数字，
必须确认它测的是它声称要测的那个量**。若当初有人把断言写成
"退出码 > 0"，这次契约修正就不会被任何测试挡下。
因此新测试对"三个数恰好相等"的 fixture 也分开断言，
避免靠数字巧合互相掩盖。

## 验证

真实 CLI 逐例比对磁盘内容（子进程，非函数级断言）：

| 场景 | found | auto_safe | applied | 磁盘 | 退出码 |
| --- | --- | --- | --- | --- | --- |
| 仅 report-only（目录） | 1 | 0 | 0 | 未变 | 0 |
| 仅 report-only（单文件） | 1 | 0 | 0 | 未变 | 0 |
| 混合 auto-safe + report-only | 2 | 1 | 1 | 仅 auto-safe 那个被改 | 0 |
| dry-run | 2 | 1 | 0 | 未变 | 1 |
| 健康代码库 | 0 | 0 | 0 | 未变 | 0 |

### 变异验证（三处，先确认变异生效）

1. `_fix_single_file` 改回返回 `found` 作为 `applied`
   → 生效（CLI 输出 `✅ Fixes applied: 1/1` 而磁盘未变）
   → 实测 **3 failed / 2 passed**
2. 抹掉 `applied == 0 and found > 0` 分支，直接打印 `✅ No fixes needed`
   → 首轮**被变异 1 掩盖**（探针走了 `applied=1` 分支，未触达目标分支）。
     先还原变异 1 再复测 → 生效（输出 `✅ No fixes needed` 而 found=1）
     → 实测 **1 failed / 4 passed**
3. 单文件退出码改回 `found`
   → 生效（未修改任何文件却退出码=1）
   → 实测 **3 failed / 14 passed**

第 2 处变异是本轮唯一一次"假阴性"：变异被前置变异遮蔽，
若只看"3 failed"会误以为它生效了。**每次变异都必须单独确认生效**，
不能借用其他变异的输出。

## 影响

- `ast-fix` 现在会明确区分"已应用 N 项"与"另有 M 项待人工确认"，
  两者不再合并为一个数字。
- 退出码语义**未变**（仍是 auto-safe 修复数），无兼容性问题。
- 与 ADR-064/065/066/067 构成同源序列：全部属于
  "报告状态与真实状态脱节"，只是脱节的位置逐层上移
  （引擎内部 → 路径存在性 → 落盘 → 分级 → CLI 措辞）。

## 相关 ADR

- ADR-067：auto_safe 只授予语义安全的改写（本 ADR 由其复验时发现）
- ADR-066：ASTFixer 报告的修复必须真正落盘（`applied_fixes` 的来源）
- ADR-065：路径不存在必须显式失败
