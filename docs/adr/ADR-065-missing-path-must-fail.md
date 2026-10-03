# ADR-065: 路径不存在必须显式失败，禁止空集合假绿灯

## 状态

接受

## 日期

2026-10-03

## 上下文

[ADR-064](ADR-064-semantic-degradation-must-be-visible.md) 修掉了 checker 层的
"降级静默"：AST 不可用时返回空 issue 列表，报告层渲染成 `PASS ✅`。
收口时顺带记录的遗留项之一是：

> `phase_runner` 对不存在的路径输出 `✅ ALL CLEAN` 且 exit 0。

本 ADR 处理该项。实测确认缺陷真实存在，且**范围比记录更广**。

## 决策

`phase_runner` 的每个 phase 函数在使用 `path` 之前必须先校验其存在性：

```python
if not path.exists():
    print(f"❌ 路径不存在: {path}")
    return 1
```

## 实测证据

### 一、同一缺陷有三个入口

原实现中，三个 phase 函数都在无校验的情况下把 `path` 交给下层，
而下游 API 对不存在的路径**不报错**，而是返回空集合：

| phase 函数 | 下游调用 | 空集合被渲染成 |
| --- | --- | --- |
| `_run_semantic_check` | `check_directory` | `✅ ALL CLEAN` |
| `_run_ast_fix` | `path.rglob("*.py")` | `✅ No fixes needed` |
| `_run_hallucination_scan` | `detect_hallucinations` | `✅ No hallucination patterns detected` |

修复前实测（`--path <不存在的目录>`）：

```
  Scanned 0 files, found 0 semantic issues
  ✅ ALL CLEAN
EXITCODE: 0
```

三种命令全部 exit 0。关键问题不是"漏检了文件"，而是
**"检查了 0 个文件"与"检查通过"在输出上完全不可分辨** ——
这与 ADR-064 根除的假绿灯同源。

`hallucination-scan` 不在原遗留记录中，是本轮修复时按同一模式
主动排查新发现的。

### 二、修复后

```
semantic-check:      exit=1 | ❌ 路径不存在: <path>
ast-fix:             exit=1 | ❌ 路径不存在: <path>
hallucination-scan:  exit=1 | ❌ 路径不存在: <path>
```

真实路径未被误伤：`semantic-check tools/scripts/hooks` 扫描 11 个文件、
报告 694 个真实问题、exit 1；干净探针文件 exit 0。

### 三、旧契约曾被测试显式断言

修复后全量测试出现 2 个失败：
`tests/test_phase2_5_integration.py::test_semantic_check_dispatch`
与 `test_ast_fix_dispatch`。检查后发现它们**不是**无关回归，
而是把假绿灯写成了预期契约：

```python
# Should not crash, returns 0 for empty/nonexistent path
result = _dispatch(args)
assert result == 0  # Empty path = 0 files = 0 issues = pass
```

注意第二行的注释：`0 files = 0 issues = pass`。
这说明假绿灯不仅存在于实现中，还被当作**正确行为**固化进了测试。
两者已更新为 `assert result != 0`，并保留"不崩溃"这一原始意图。

值得记录的是，这三个 phase 函数此前**没有任何单元测试**
（`grep _run_semantic_check` 在 `tests/` 下 0 命中），
唯一的覆盖来自这两个集成用例，而它们锁定的正是错误行为。

### 四、变异验证

删除三处校验后重跑 `tests/test_phase_runner_missing_path.py`：

```
3 failed, 3 passed
```

失败的正是三个缺陷检测用例，通过的正是三个对照组用例 ——
说明对照组没有被变异波及，测试确实锚定在缺陷上而非笼统的退出码。

## 关键发现：对照组是这类测试的必需品

本缺陷若只写"缺失路径必须 exit 非零"的断言，一个**无脑 `return 1`**
的实现也能让全部用例通过。同样的陷阱在 Phase 40 已出现过四次
（返回值口径搞错、测试用例用不含 `def` 的文件、探针赋错局部
`from`-import 名字、探针文件不含可修复缺陷）。

因此本 ADR 的测试强制包含三类对照：

1. **干净文件** `semantic-check` 必须 exit 0 —— 探针刻意不含 `def`，
   否则必然命中 `py-missing-all` 规则，断言会因无关原因失败。
2. **干净目录** `ast-fix --dry-run` 必须 exit 0。
3. **干净目录** `hallucination-scan` 必须 exit 0。

## 备选方案

- **让下游 API 对不存在路径抛异常**：影响面更大，且
  `check_directory` 等函数被多处复用，改动风险高于收益。
  本地校验是更小、更可测的闭环。
- **复用 CLI 层统一校验**：`hooks_runner` 有多处子命令共享 `--path`，
  在参数解析层统一校验可一次覆盖更多命令。本轮未采用，
  因为 phase 函数可被 `hooks.json` 直接调用，不保证经过参数解析层。
  留作后续统一治理项。

## 影响

- **行为变更**：对不存在路径的调用由 exit 0 变为 exit 1。
  这是有意的 —— 前者是假绿灯。若有 CI 依赖旧的宽松行为，
  会在路径配置错误时开始失败，这正是期望效果。
- 真实路径行为不变，由三个对照组用例锁定。

## 相关 ADR

- ADR-064：语义检查降级必须可见（同源假绿灯的另一处）
- ADR-063：tree-sitter 导入必须按语言粒度容错
