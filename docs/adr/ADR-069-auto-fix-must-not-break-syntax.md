# ADR-069: 自动修复不得产出无法解析的代码

## 状态

接受

## 日期

2026-10-03

## 影响组件

- `tools/scripts/rules_engine/ast_fixer.py`（`_fix_empty_functions`）
- `tests/test_ast_fixer_inline_body_safety.py`

## 背景

ADR-067 收敛 `auto_safe` 后，`tools/scripts` 上仅剩 2 处 auto-safe 修复。
为核实"这 2 处是否安全"，我用 `fix_file(dry_run=False)` 扫描了全仓
209 个文件——**探针本身把两个文件改坏了**：

```
 tools/scripts/hooks/domain_checks.py | 1 +
 tools/scripts/rules_engine/parsers/contract.py | 1 +
```

两处插入的都是 `pass`。还原后单独复现，得到确切后果：

```
$ hooks_runner.py ast-fix --path <Protocol 探针>
      Total fixes found: 1 (1 auto-safe)
      Fixes applied: 1
      ✅ Fixes applied: 1/1
$ cat p.py
class P(Protocol):
    def audit(self) -> bool: ...
        pass
$ python -c "import ast; ast.parse(open('p.py').read())"
IndentationError: unexpected indent
```

CLI 报告成功，磁盘内容**不再能被解析**。

## 缺陷根因

`_fix_empty_functions` 的判据是"def 的**下一行**是否为空"，
从不检查 def 行自身是否已带 `: ...` 同行体。`body_lines <= 1`
同时涵盖两种本质不同的情形：

| 情形 | 实际语义 | 原实现处理 |
| --- | --- | --- |
| 体与 def 同行（`: ...`） | **已有体** | 误判为空 → 插入 pass |
| 体在下一行且为空 | 确实无体 | 正确插入 |

## 决策

用 `FunctionInfo.end_line` 判定：`end_lineno == lineno` 即同行体，
此时跳过。**不用文本找冒号**——`def f(self, x: int = 3):` 的首个
冒号属于参数注解，`partition(":")` 会把它误判为有体（实测确认）。

## 关于"过度纠正"的实测结论

我额外做了一次反向变异（把守卫改成恒真，即永不修复），
**5 个测试全部通过**——说明没有测试守住"真正空体仍被修复"。

追查后确认这不是测试缺口而是**该分支实际不可达**：

- Python 不允许空函数体，任何"确实无体"的源码在解析阶段就失败，
  根本进不到本规则；
- 基线态全仓扫描 209 个文件，`fix-empty-function` **仅 2 处触发，
  且两处都是同行 `...` 体**。

即：本规则在真实代码库里的**唯一实际效果就是破坏合法代码**。
修复后触发数归 0，属预期结果而非回归。这一点已写入规则 docstring，
避免后续维护者误判为规则失效。

## 验证

- 端到端：原复现输入经 `ast-fix` 后磁盘内容不变且 `ast.parse` 通过；
  `Total fixes found: 0`。
- 混合场景：协议方法不动、`fix-bare-except` 仍正常修复、整体可解析。
- 真实对照：仓库内 `parsers/contract.py`（含真实 Protocol 定义）
  经 `ast-fix` 后逐字节不变。
- 变异验证（两处，先确认生效）：
  1. 移除 `end_line` 守卫 → 生效（复现 IndentationError）
     → 实测 **5 failed / 5 passed**
  2. 守卫改恒真（过度纠正）→ 生效（触发数归 0）
     → 实测 **5 passed**，据此得出"该分支不可达"的结论

### 变异验证中的一次假阴性

首轮变异后测试只报 **2 failed**，我据此以为变异生效。
但直接看 CLI 输出却是 `✅ No fixes needed`——**变异根本没生效**：
探针输入少了尾随空行，解析器不把该函数纳入待修复集合，
`found=0`，自然不会触发插入。

去掉尾随空行后缺陷不复现，加上才复现。触发条件比"同行体"
更窄。若当时只看 failed 数，会把"变异未生效"误判为"测试不够严"。

## 影响

- 本仓库的 2 处 Protocol 方法不再被 `ast-fix` 损坏。
- 结论升级：ADR-064~068 五处假绿灯都是**报告与真实状态脱节**，
  本处是**报告成功却实际破坏了代码**，严重性高一档。

## 对其余规则的核查（实测，非推断）

我在初稿里把"其余规则未做同样校验"列为遗留风险，随后逐条实测，
结论是**该风险表述过重**，据实修正：

| 规则 | auto_safe | 实测结论 |
| --- | --- | --- |
| `fix-bare-except` | True | 用 `^(\s*)except\s*:\s*$` 锚定整行，安全 |
| `fix-empty-except` | False（ADR-067） | 只报告不落盘，无法破坏代码 |
| `fix-unused-var` | False | 见下 |
| `fix-empty-function` | True | **本 ADR 修复对象** |
| `suggest-refactor` | False | 空替换，纯建议 |

`fix-unused-var` 的判据是 `content.count(var_name) - 1 <= 0`，
即**子串计数**。我担心它会误改实际被使用的变量，实测四个场景：

| 场景 | 是否报告 |
| --- | --- |
| 真正未使用 | 是（正确） |
| 跨函数同名使用 | 否 |
| 字符串中出现 | 否 |
| 属性访问同名 | 否 |

子串计数**只会多算、不会少算**，因此只会产生漏报（漏掉本该改的），
不会产生误报（改掉不该改的）。加上它是 report-only、不落盘，
两个因素叠加后它无法破坏代码。

**仍然成立的建议**：`fix_file` 写回前加一道 `ast.parse` 自检、
失败则拒绝写盘。这是纵深防御——本 ADR 证明逐条规则修补
容易漏（我差点就漏了 `fix-unused-var` 的核查）。此项**未实施**。

## 相关 ADR

- ADR-068：ast-fix 报告必须区分"发现"与"已应用"（本 ADR 修复前的复验由其触发）
- ADR-067：auto_safe 只授予语义安全的改写（本 ADR 是其遗留风险的最终暴露）
- ADR-066：ASTFixer 报告的修复必须真正落盘
