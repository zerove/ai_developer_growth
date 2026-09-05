# ADR-049: Phase 33b-8 ast_parser 多语言 walk 与 complexity 迭代化扩展

## 状态
接受

## 日期
2026-09-05

## 背景

ADR-048 (33b-7) 修复了 5 个 walk 函数的 RecursionError (`_walk_python_functions` / `_walk_classes` / `_walk_imports` / `_find_error_nodes` / `_count_nodes`)。

但**遗漏了 5 个其他递归函数**:
- `_walk_js_functions` (line 468) — JS/TS AST 遍历
- `_walk_rust_functions` (line 546) — Rust AST 遍历
- `_walk_go_functions` (line 606) — Go AST 遍历
- `_walk_generic_functions` (line 705) — 通用 fallback
- `_count_branching_static` (line 149) — 复杂度计算的递归计数

这 5 个函数也是**纯递归**, 触发条件与 ADR-048 相同 (深度 binary_expression 链 / 长 boolean_operation)。

**实际场景**:
- JS/TS 项目使用深度链式三元表达式 / 嵌套对象字面量
- Rust 项目使用深度 if/else 链
- Go 项目使用深度函数调用
- 任何项目的 `if a and b and c and d...` 长 boolean chain
- `complexity` 计算本身也会爆栈

## 决策

### 决策 1: 5 个 walk/count 函数统一迭代化

延续 ADR-048 模式 (栈 + `reversed(children)` 保 depth-first 顺序):
- `_walk_js_functions`: 栈元素 `(node, class_name)`, 保留 class_body 内部成员用 inner class_name
- `_walk_rust_functions`: 栈元素 `(node, class_name)`, impl_item 内用 type_name
- `_walk_go_functions`: 栈元素 `(node, class_name)`, 简单 dispatch
- `_walk_generic_functions`: 栈元素 `(node, class_name)`, func_patterns 匹配
- `_count_branching_static`: 栈元素 `node`, 简单 count

### 决策 2: 不修改 `_walk_python_globals`

`_walk_python_globals` (line 1106) **只走一层** (`for child in node.children:`), **不递归调用自身**。它不会爆栈, 跳过即可。

### 决策 3: boolean_operation 不计入复杂度 (设计选择)

测试发现 boolean_operation (a and b and c...) 不在 `branching_types` 集合中 (line 133-143)。这是**已有设计**: boolean_operation 是 short-circuit 表达式, 与 if/while 等控制流不同。深度 boolean 链只验证"不爆栈", 不验证复杂度计数。

## 后果

### 正面
- **全部 9 个 walk/count 函数迭代化** (ADR-048 5 个 + 本 ADR 5 个)
- 多语言 (JS/Rust/Go) 深度 AST 安全性提升
- 复杂度计算无栈溢出风险
- 覆盖率 88.02% → **88.16%** (+0.14%)

### 负面
- 5 个函数改动加大总变更面 (10 个 walk + count 函数迭代化)
- boolean_operation 测试用例与最初预期不符 (复杂度不递增), 调整断言为 `== 1`

## 验证

- 15/15 `test_ast_parser_recursion.py` 通过 (含 4 个多语言 + 2 个 complexity 深度测试)
- 252 个相关测试全过 (ast_parser / semantic_rules / semantic_checker / phase2_5)
- 3934/3934 全量测试通过
- quality-gate: 192 passed, 0 failed
- baseline: 19 (12 文件) 一致
- typecheck: 192 source files 无问题
- lint: All checks passed

## 累计状态

- 49+1=50 ADR (含本 ADR)
- 11 降级规则 (baseline.json)
- 3928+6=3934 tests passed (6 新测试)
- 88.16% 总覆盖率
- **ast_parser 完整迭代化**: 9 个 walk/count 函数全部修复
- 深度 AST 安全: 1000+ 链安全 (多语言)