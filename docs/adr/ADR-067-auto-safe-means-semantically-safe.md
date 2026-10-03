# ADR-067: auto_safe 只授予语义安全的改写

## 状态

接受

## 日期

2026-10-03

## 上下文

[ADR-066](ADR-066-ast-fixer-must-persist-fixes.md) 让 `ASTFixer.fix_file`
真正写盘，并记录了一个当时未处理的风险：

> 实测 `ast-fix --path tools/scripts --dry-run` 有 204 处 auto-safe
> 修复，抽样查看全部是 `fix-empty-except`。

本 ADR 处理该项。

## 决策

`auto_safe=True` 只授予「语义等价且质量提升」的改写，
不授予「仅仅是把问题标出来」的建议。

据此把 `fix-empty-except` 从 `auto_safe=True` 降级为 `False`，
并修正其 `description`（原为 `"Add logging for silenced exception"`，
但它实际插入的是 `# TODO` 注释，**根本没有加日志**）。

## 分级原则

审计 `ast_fixer.py` 全部 5 条规则：

| rule_id | 改写内容 | auto_safe | 判定 |
| --- | --- | --- | --- |
| `fix-bare-except` | `except:` → `except Exception:` | True | 语义等价改写，正确 |
| `fix-empty-except` | `pass` → `pass  # TODO: ...` | ~~True~~ → **False** | **仅标记问题，降级** |
| `fix-unused-var` | `x` → `_x` | False | 本就需审查 |
| `fix-empty-function` | 插入 `pass` | True | 使代码可运行，正确 |
| `suggest-refactor` | 空替换（纯建议） | False | 本就不是改写 |

只有 `fix-empty-except` 被误标。它与 `fix-bare-except` 同为
`auto_safe=True`，却混淆了两件不同的事：

- `except:` → `except Exception:` **消除问题**
- `pass` → `pass  # TODO: Handle this exception` **标记问题**

后者降低代码质量——批量注入 TODO 会让代码库更糟。

## 实测证据

### 一、降级前后对比（真实代码库）

```
降级前: ast-fix --path tools/scripts --dry-run
        → 204 处 [AUTO]，抽样全为 fix-empty-except

降级后: ast-fix --path tools/scripts --dry-run
        → 2 处 [AUTO]
        → 25 处 fix-empty-except 仍被报告（交人工决定）
```

**204 → 2**，同时 25 处发现能力完全保留。降级只影响
"是否自动应用"，不影响"是否被发现"。

### 二、探针验证

```
=== 修复后磁盘内容 ===
def f():
    try:
        pass
    except Exception:
        pass
--- TODO 计数（应为 0）---
0
--- 裸 except 仍被正确修复 ---
1
```

真正的修复照常落盘，TODO 注入消失。

### 三、双向变异验证

只验证"降级生效"是不够的——过度纠正（把真正安全的规则也降级）
同样是缺陷。故做双向变异（脚本内断言确认均已生效）：

| 变异 | 结果 |
| --- | --- |
| `fix-empty-except` 还原为 `True` | 被 `test_empty_except_is_not_auto_safe` 捕捉 |
| `fix-bare-except` 降级为 `False` | 被 `test_bare_except_remains_auto_safe` 捕捉 |

合计 **8 failed / 9 passed**，两个方向都有用例守住。

## 关键发现：降级修正了两个源自 ADR-066 的过时断言

降级后 `test_ast_fixer_persistence.py` 出现 2 个失败。检查发现
是**断言写错了**，不是实现有问题：

1. `test_applied_fixes_reflects_reality` 原断言
   `applied_fixes == total_fixes`。降级后本探针 2 项中 1 项是
   report-only，正确结果是 `1 != 2`。
   ADR-066 引入 `applied_fixes` 的**初衷**就是让这两个数可以不等
   —— 当时的测试却断言它们必须相等，自相矛盾。
   已改为 `applied_fixes == auto_safe_fixes` 且 `<= total_fixes`。

2. `test_rerun_on_fixed_file_finds_nothing` 原断言
   `total_fixes == 0`。降级后 `fix-empty-except` 是 report-only，
   仍会发现并建议插入 TODO（`total_fixes=1, applied_fixes=0`）。
   幂等性真正要保证的是"不重复**应用**"，已改为 `applied_fixes == 0`。

两个修正都指向同一件事：**"发现"与"应用"是两个不同的量**，
断言必须分别对准。ADR-066 引入 `applied_fixes` 时没意识到这一点，
导致测试固化了错误的等式。

## 影响

- `ast-fix` 对本仓库趋于无操作（2 处 auto-safe），裸 `except`
  这类真实改进不再被批量应用——这是意图。
- 25 处被静默吞掉的异常仍出现在报告中，退出码与输出可见。
- `fix-bare-except` 等真正的语义安全改写能力完全保留。

## 相关 ADR

- ADR-066：ASTFixer 报告的修复必须真正落盘（本 ADR 处理其遗留风险）
- ADR-065：路径不存在必须显式失败
- ADR-064：语义检查降级必须可见
