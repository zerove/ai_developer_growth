# ADR-064: 语义检查降级必须可见，禁止 fail-open

## 状态

接受

## 日期

2026-10-03

## 上下文

[ADR-063](ADR-063-tree-sitter-per-language-import.md) 收窄了 AST 不可用的触发条件，
并在"遗留"一节明确留话：

> AST 不可用时 `parse_file` 仍返回 `None`（而非抛异常），
> 调用方的 fail-open 面依然存在。

Phase 40 处理这条遗留。实测确认缺陷真实存在，且比预想更隐蔽。

### 实测证据一：checker 层静默返回空

`checker._run_semantic_checks` 的原实现：

```python
parser = get_parser()
if not parser.available:
    return issues          # issues == []，静默

ast_result = parser.parse_file(filepath)
if ast_result is None:
    return issues          # 静默

try:
    ...
except ImportError:
    pass                   # 静默
except Exception:
    pass                   # 静默
```

调用方拿到空列表，**无法区分"检查通过"与"检查根本没跑"**。
实测数据：屏蔽全部 tree-sitter 后 `SemanticChecker` 报
`files_analyzed=0, issues=0`；依赖齐全时同一目录报 54 个问题。
两者输出形态完全一致，看起来像"代码完美"。

### 实测证据二：真实 hook 路径打出绿灯

`hooks_runner semantic-check` 在旧实现下对一个无任何规则命中的文件
输出 `EXITCODE: 0`。这不是理论推断，是子进程实测捕获的 stdout。

### 关键发现：info 严重度救不了场

第一版修复把降级 Issue 定为 `severity="info"`，理由是"info 不阻断构建"。
实测证明这是错的 —— `CheckResult.passed` 只看 `error_count`
（`models.py:57`）：

| severity | `passed` | report_generator 渲染 |
| --- | --- | --- |
| `info` | `True` | **PASS ✅** |
| `warning` | `True` | **PASS ✅** |
| `error` | `False` | FAIL ❌ |

即 info 与 warning 都会把"检查根本没跑"重新渲染成绿灯，
等于换个地方复现同一个假绿灯。**只有 error 能真正可见。**

### 为什么 error 不会误伤常规门禁

已核验两个前提：

1. 全仓仅 `phase_runner._run_semantic_check` 以 `semantic=True` 调用检查器；
2. `.jcode/hooks.json` 的 on_commit / on_pr / on_merge / scheduled
   **均未触发** semantic-check。

即"显式要求语义检查却没跑成"才会产生 error，属于名副其实的错误，
而常规 lint / quality-gate 路径（`semantic=False`）完全不受影响。

## 决策

1. **降级必须产出 Issue**，规则 ID 统一为 `semantic-degraded`，
   严重度为 `error`，category 为 `infrastructure`。
2. **区分降级原因**，不再一律 `return issues`：
   - tree-sitter 整体缺失 → `tree-sitter 未安装`
   - 指定语言解析器缺失 → `{lang} 的解析器不可用`
   - 语言存在但解析失败 → `{lang} 文件解析失败`
   - 依赖导入失败 → `语义检查依赖缺失: {exc}`
   - 其他异常 → `语义分析异常: {Type}: {exc}`
3. **禁止 `except: pass`**：异常分支同样产出降级 Issue，
   保证"检查没跑成"这件事在任何情况下都有痕迹。

## 后果

- **正面**：真实 hook 路径从 `EXITCODE: 0`（假绿灯）变为 `EXITCODE: 1`
  并打印 60 条 `semantic-degraded`；健康路径输出完全不变
  （1238 issues / 0 条降级），无回归。
- **代价**：`semantic=True` 的调用方在缺依赖时会拿到 error 并失败。
  这是有意的 —— 显式要求语义检查却没跑成，本就该失败。
- **口径纠正**：实测中发现 `check_directory` 返回的是
  `list[CheckResult]` 而非 issue 列表。首次测量误将其当 issue 列表，
  导致 `getattr(rule_id)` 恒为空、错误地得出"降级不可见"的结论。
  正确口径：基线 1238 issues / 0 降级，降级后 1257 / 60 降级
  （1197 regex + 41 AST = 1238；1197 + 60 = 1257，账目自洽）。
- **未修复的同源缺陷**：`ast_fixer` 存在同类问题。实测
  `hooks_runner ast-fix` 在健康与降级两种环境下**均 exit 0 且零输出**，
  修复者完全无法分辨。本 ADR 未涵盖，留作独立后续项。
  `SemanticChecker` 亦然，但实测其仅在模块 docstring 中被示例引用，
  无生产消费方，优先级低于 `ast_fixer`。

## 相关 ADR

- ADR-063：tree-sitter 导入必须按语言粒度容错（本 ADR 收口其遗留项）
- ADR-062：fail-open 检测器必须校验"可执行性"，而非匹配错误关键词

## 验证方式

`tests/test_semantic_degraded_visibility.py`（8 用例）。

关键要求：全部在**子进程**中、于导入检查器**之前**屏蔽包
（沿用 ADR-063 变异测试确立的方法论）。

变异验证（用 `git show HEAD:checker.py` 取回真实旧实现，非手写模拟）：

- 旧实现：**6 failed / 2 passed**
- 新实现：**8 passed**

其中 `test_hook_path_exits_nonzero_when_degraded` 在旧实现下捕获到
`EXITCODE: 0`，直接复现假绿灯。该用例的探针文件必须**不含 `def`**：
含 `def` 时 `py-missing-all` 规则必然命中，无论是否降级都 exit 1，
断言形同虚设 —— 此缺陷由变异测试暴露后改为 `X = 1`。
