# ADR-070: 写盘前必须校验修复结果的语法

## 状态

接受

## 日期

2026-10-03

## 影响组件

- `tools/scripts/rules_engine/ast_fixer.py`（`_verify_syntax`、`fix_file`、`FixReport`）
- `tools/scripts/hooks/phase_runner.py`（`FileFixResult`、`_fix_single_file`、`_print_directory_summary`）
- `tests/test_ast_fixer_write_verification.py`

## 背景

ADR-069 修好了 `fix-empty-function` 这一个具体缺陷，但它采用的是
**逐条规则加守卫**的修法。守卫的有效性依赖一个假设：

> 每个规则的守卫都覆盖了该规则所有会产生非法代码的路径。

这个假设无法独立验证——一旦某个规则有第二条产生非法代码的路径，
或在后续重构中引入新路径，守卫就静默失效，而 CLI 依然会打印
`✅ Fixes applied`。ADR-069 本身已经展示了这种脆弱性：我差点就漏掉
`fix-unused-var` 的核查，是靠逐条实测才发现它无需处理。

更关键的是，本仓库**已有的语法解析能力对这类缺陷是瞎的**。
见下文"否决的方案"。

## 决策

在 `fix_file` 的**写盘这一层**加一道与具体规则无关的兜底：

1. 修复结果在写盘前必须通过语法校验；不通过则**整体回退**，
   一个字节都不写。
2. 回退时 `applied_fixes` 归 `0`，并置 `syntax_violation=True`。
   报告仍如实给出发现数与 auto-safe 数——它们与 `applied` 的差距
   正是要告诉用户的信息。
3. `fixed_content` 回退为原始内容，避免下游拿到被破坏的文本。
4. CLI 在**明细**里给出具体语法错误，在**汇总**里给出被拒文件数，
   且该汇总行的优先级**高于** `✅ Fixes applied`。

## 否决的方案：用现成的 tree-sitter 自检

项目已有 tree-sitter 多语言解析器（12 种语言），最自然的做法是直接
拿它做写盘前校验。**实测否决**：

```python
broken = "class P(Protocol):\n    def audit(self) -> bool: ...\n        pass\n"
tree_sitter.parse(broken, "python").root_node.has_error  # False
ast.parse(broken)  # IndentationError
```

tree-sitter 对 ADR-069 那份被破坏的代码 `has_error=False`——
它**看不见** `IndentationError`，而 `ast.parse` 能看见。

为确认这不是个例，我比对了两种判定在本仓库全部 Python 文件上的
一致性：**681 个文件，0 处分歧**。也就是说两种方式在"正常代码"上
表现完全一致，**恰恰在关键样本上不一致**——只看一致性统计会得出
"tree-sitter 够用"的错误结论。

因此判定规则是：

| 语言 | 校验器 |
| --- | --- |
| Python | `ast.parse`（`ast.parse` 是唯一可信来源） |
| 其余 | tree-sitter `root_node.has_error` |

非 Python 语言的兜底强度弱于 Python（tree-sitter 的 error 节点
检测对缩进类问题不敏感），这是已知限制，见"遗留限制"。

## 三态而非两态

`FixReport.syntax_violation` 用 `True / False / None` 三态：

| 值 | 含义 |
| --- | --- |
| `True` | 自检跑了且**失败**，已拒绝写盘 |
| `False` | 自检跑了且通过 |
| `None` | **自检没跑**（dry-run / 内容无变化 / 校验器不可用） |

两态（`True` / `False`）不够：把"通过"和"没检查"都记作 `False`，
调用方就无法区分"已验证安全"与"根本不知道"，兜底本身变成不可观测的。
这个设计缺陷是被测试断言 `is False` 而非 `falsy` 逼出来的——
初版实现返回 `None` 时，断言失败才暴露了语义混淆。

## 验证

### 真实 CLI 端到端

以 `sitecustomize` 注入把 `fix-empty-function` 换回 ADR-069 之前的实现
（只 patch 方法，不改 `ast_fixer.py` 源码），走完整子进程链路：

```
$ PYTHONPATH=<inject> hooks_runner.py ast-fix --path probe.py
[AUTO] fix-empty-function (line 3)
  +         pass

  ❌ 拒绝写盘: 修复结果无法解析 (ADR-070)
      IndentationError: unexpected indent (<unknown>, line 3)
      文件保持原样, 请人工处理后重试

  Total fixes found: 1 (1 auto-safe)
  Fixes applied: 0
  ❌ 1 file(s) rejected: fixes would break syntax (ADR-070)
  ❌ Syntax check failed — see messages above
```

磁盘内容逐字节不变，`ast.parse` 通过。

**为何 CLI 用例必须注入**：ADR-069 已修，同行 `: ...` 体不再产生修复项，
破坏路径在正常子进程中**不可达**。初版 CLI 用例因此报
`汇总未提及语法自检`，但那是**假失败**——它没测到兜底，只是测到
守卫还在。注入后才真正驱动到兜底分支。

### 变异验证（三处，逐处确认生效）

| 变异 | 注入方式 | 实测结果 |
| --- | --- | --- |
| A：`ast.parse` 自检被短路 | 改源码 | **7 failed**（CLI 退化回 `✅ Fixes applied: 1/1`，磁盘真实被破坏） |
| B：汇总不再优先报语法失败 | 改源码 | **2 failed**（输出退化为 `✅ Fixes applied: 1/3`——部分成功却报绿） |
| C：单文件明细提示被删 | 改源码 | 首轮 **12 passed** → 补断言后 **1 failed** |

变异 A 的实际输出已单独复核，确认退化形态就是 ADR-070 前的假绿灯：

```
  Fixes applied: 1
  ✅ Fixes applied: 1/1
$ cat probe.py
class P(Protocol):
    def audit(self) -> bool: ...
        pass          ← 文件确实被破坏
```

### 变异 C 暴露的测试缺口

变异 C 首轮 **12 passed**——删掉明细里的错误提示后测试全绿，
因为断言只检查了汇总行。但汇总写的是
`Files left unchanged. Fix the reported syntax error manually.`
和 `see messages above`，而 "above" 里**根本没有那条消息**——
汇总在指向虚空，用户只知道"被拒"却无从下手。

补断言 `拒绝写盘` 与 `IndentationError` 必须出现在输出中后，变异 C
变为 1 failed。这是本轮三次变异里唯一一次"通过数不降反升"，
也是只看 failed 数会漏掉的情形。

### 收口时发现的另一处假绿灯：测试防护本身已失效

本 ADR 全量回归时出现 6 项失败（`test_ast_parser_partial_install`
2 项、`test_semantic_degraded_visibility` 4 项）。在 `84ce30a` 的干净
检出上复现同样失败，**与本次改动无关**——但归因后发现它属于同一类
假绿灯，且比代码报绿更隐蔽：

`test_ast_parser_partial_install.py` 与 `test_semantic_degraded_visibility.py`
里的 `_BlockingFinder` 只实现了 `find_module` / `load_module`。这两个方法
属于 Python 3.12 **已移除**的旧导入协议，导入系统不再回退到它们，
该 finder 被**完全忽略**——被屏蔽的包照常导入成功。两个文件实际上早已
**丧失**对 Phase 38「全有全无导入」缺陷的回归保护，却一直在为绿灯贡献计数。

```python
# 修复前: 屏蔽从未生效。实现 PEP 451 的 find_spec 才会被导入系统调用
class _BlockingFinder:
    def find_spec(self, name, path=None, target=None):
        if name in BLOCKED:
            raise ImportError("simulated missing package: " + name)
        return None
```

迁移后 14 个用例全绿。但**通过不等于防护有效**，故按上文同一判据
做变异：对 `ASTParser._shared_parsers` 注入 Phase 38 之前的全有全无行为
（缺任一语言即整体失败），确认 **2 failed**，且 `ImportError` 明确指向
注入行——若屏蔽器再次失效，`missing` 会为空，`raise` 根本不会触发。
还原源文件后 14 项重新全绿。

结论：**green ≠ protected**。上一阶段记录的"4575 passed"本身就掺了这 6 项
失效防护，是一次未经察觉的假绿灯；本阶段修复后全量为 **4587 passed**。

## 对 ADR-068 的勘误

ADR-068 初稿把 `_apply_fix` 行号越界列为 `applied < auto_safe`
的成因之一。Phase 45 以 `fix_file(dry_run=False)` 扫全仓 209 个
文件实测，该路径 **0 次触发**——守卫存在，但从未被走到。

故它应标注为**未观测路径**而非已发生事实。已实测的成因是：
ADR-067 的 report-only 规则，以及本 ADR 的语法自检拒绝写盘。
ADR-068 正文、`FixReport` 注释、`FileFixResult` docstring 与
`test_ast_fixer_persistence.py` 的 docstring 均已同步降级。

## 遗留限制

- **非 Python 语言兜底较弱**：tree-sitter 对缩进类语法问题的检测
  不敏感（见上文实测）。仓库内 45 个非 Python 文件实测
  `has_error=True` 为 0 个，说明当前无误拒，但也说明这条路径
  **未经真实破坏样本验证**。若将来为 Rust/Go 等语言新增修复规则，
  应先构造破坏样本验证 tree-sitter 能否检出。
- **只覆盖 `ASTFixer.fix_file`**：`tools/fix_engine/FixEngine.fix_file`
  是另一条独立写盘路径（正则替换 + YAML 规则），本次**未加兜底**。
  该路径的规则（如 `CQ002` 把 `print(...)` 换成 `logger.info(...)`）
  有改变语义的风险，但同样不验证语法。属未实施候选。
- **`fix_content` 未加兜底**：它是纯函数、不落盘，返回值由调用方决定
  是否写入，故未改。

## 相关 ADR

- ADR-069：自动修复不得产出无法解析的代码（本 ADR 是其遗留建议的实施）
- ADR-068：ast-fix 报告必须区分"发现"与"已应用"
- ADR-067：auto_safe 只授予语义安全的改写
- ADR-066：ASTFixer 报告的修复必须真正落盘
