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
    return issues  # issues == []，静默

ast_result = parser.parse_file(filepath)
if ast_result is None:
    return issues  # 静默

try:
    ...
except ImportError:
    pass  # 静默
except Exception:
    pass  # 静默
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
（`tools/scripts/rules_engine/models.py:121`，`CheckResult` 类体起于 112 行；
`ValidationResult.passed` 在 57 行，是另一个类，本处引用的是前者）：

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
4. **只用公开 API**：判定解析器缺失用 `parser.supported_languages()`，
   不碰私有 `parser._parsers`。

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
- **未修复的同源缺陷**：`ast_fixer` 的缺陷范围比初版记录**窄**，
  但 Phase 42 的实测又把它改判为**更严重的一类**。四种组合实测：

  | 调用方式 | 健康环境 | 降级环境 |
  | --- | --- | --- |
  | 目录（`verbose=True`） | `Total fixes: 2` + 明细 | `⚠️ Cannot parse ..., skipping`，`exit=0` |
  | 单文件（`verbose=False`） | 仅标题，`exit=2` | 仅标题，`exit=0` |

  两处需要纠正本 ADR 初版复核的表述：

  1. **"两种环境 exit 都是 0"错误**。单文件路径把 `total_fixes`
     直接当返回码，健康环境有修复时 `exit=2`，降级时 `exit=0`。
     即降级确实**丢失了退出码信号**，但健康路径没有。
  2. 更关键的是，`exit=2` 所代表的"修复"**从未落盘**。
     `ASTFixer.fix_file`（`ast_fixer.py:102-106`）算出 `fixed_content`
     后**从不写回文件**，实测裸 `except` 在非 dry-run 运行后依然存在：

     ```
     fix_file 返回: FixReport
     total_fixes = 2
     fixes 明细: rule='fix-empty-except' line=9 auto_safe=True
                 rule='fix-bare-except'  line=8 auto_safe=True
     文件是否被修改: False
     裸 except 修复前后计数: 1 -> 1
     ```

     `_apply_fix` 本身正确（`fixed_content` 内裸 `except` 计数为 0），
     缺的只是一次写回。这比"输出缺失"严重得多：CLI 报
     `✅ Fixes applied` 且 `exit=2`，用户会认为代码已改，实际未改。
     详见 ADR-066。`SemanticChecker` 亦有同源问题，但实测仅在模块
     docstring 中被示例引用，无生产消费方，优先级低于 `ast_fixer`。

- **本轮复核纠正的一处误判**：初版记录称 `ast-fix` "两环境 exit 0
  且零输出"，该结论**不成立** —— 当时探针文件不含任何可修复缺陷，
  健康环境本就无输出，与降级静默无法区分。等价于用"没有 `def` 的文件"
  犯过的同类错误（见验证方式一节）。正确探针须含
  `bare except:` / 未用变量 / 空函数等**可修复项**，
  否则变量根本没被隔离。

## 相关 ADR

- ADR-063：tree-sitter 导入必须按语言粒度容错（本 ADR 收口其遗留项）
- ADR-062：fail-open 检测器必须校验"可执行性"，而非匹配错误关键词

## 验证方式

`tests/test_semantic_degraded_visibility.py`（9 用例）。

关键要求：全部在**子进程**中、于导入检查器**之前**屏蔽包
（沿用 ADR-063 变异测试确立的方法论）。

变异验证（用 `git show c9329db^:checker.py` 取回真实旧实现，非手写模拟）：

- 旧实现：**7 failed / 2 passed**
- 新实现：**9 passed**

5 类降级原因逐一有测试覆盖。其中泛化 `except Exception` 分支原先
**零覆盖**（`grep '语义分析异常'` 仅命中实现本身），本阶段补上 ——
首次写该用例时用了不存在的 `x.py`，`parse_file` 先返回 `None`，
根本没触达目标分支；改用临时目录中的真实文件后才真正覆盖。

`test_hook_path_exits_nonzero_when_degraded` 在旧实现下捕获到
`EXITCODE: 0`，直接复现假绿灯。该用例的探针文件必须**不含 `def`**：
含 `def` 时 `py-missing-all` 规则必然命中，无论是否降级都 exit 1，
断言形同虚设 —— 此缺陷由变异测试暴露后改为 `X = 1`。

### 变异基线会随提交而失效

提交修复后 `git show HEAD:checker.py` 取回的**就是修复版**，变异静默无效，
9 个用例全部"通过"，差点得出"测试无效"的错误结论。正确基线是修复提交的
父提交 `c9329db^:`。**必须先确认变异标记真的变了再看测试结果** ——
与 ADR-063 阶段记录的 `git stash push -- <file>` 静默失效是同一类陷阱。

## 需求 → 检查 逐条追踪

下表跑在**已提交结果**（`d507a51`）上，每项均为可观测输出，非静态检查。

| 需求 | 观测结果 |
| --- | --- |
| R1 AST 不可用时降级可见 | `degraded条数: 1`，`severity: error` |
| R2a 整体缺失可区分 | 报"未安装": `True` |
| R2b 解析器缺失可区分 | 报"解析器不可用": `True`，未误报"未安装": `True` |
| R2c 分析异常可区分 | 条数 1，报"语义分析异常": `True`，**保留原异常** `True` |
| R3a 不产生假绿灯（`passed`） | `passed: False`，`error_count: 1` |
| R3b 不产生假绿灯（HTML 报告） | 渲染 PASS: `False`，渲染 FAIL: `True` |
| R4 健康路径无回归 | 61 文件 / 1238 issues / **降级 0 条** |
| R5 真实 hook CLI（健康） | `exit=0`，`semantic-degraded=0` |
| R5 真实 hook CLI（降级） | `exit=1`，`semantic-degraded=1` |

R5 的降级环境经独立确认：`HAS_TREE_SITTER=False` 是由 `sitecustomize`
探针**模拟**出来的，而非宿主环境本就缺依赖 —— 否则健康/降级对比无意义。

R2c 采集过程中出现过一次**探针自身的缺陷**：初版试图给
`ck.run_semantic_rules` 赋值，但该名字是函数内 `from` 导入的局部绑定，
赋值不生效、探针返回空列表。改为改写 `semantic_rules` 模块属性后正常。
与本 ADR 记录的测试用例首版用不存在文件同理：**探针写错会伪装成"功能缺失"**。
