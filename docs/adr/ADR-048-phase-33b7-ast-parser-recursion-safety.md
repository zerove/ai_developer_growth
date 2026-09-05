# ADR-048: Phase 33b-7 ast_parser 深度 AST 安全 (消除 RecursionError)

## 状态
接受

## 日期
2026-09-05

## 背景

按指令 "exercise edge cases, packaging, and likely failure modes" 探索 ast_parser 边界场景时发现真实 bug:

**触发条件**:
- 1+1+1+... 链式表达式 (e.g. 1000 个连续 `+`)
- tree-sitter 生成深度嵌套 binary_expression 节点 (左结合)
- 触发 Python `RecursionError: maximum recursion depth exceeded`

**根因**:
5 个内部 walk 函数是**纯递归**实现:
- `_walk_python_functions` (line 399)
- `_walk_classes` (line 741)
- `_walk_imports` (line 1047)
- `_find_error_nodes` (line 1109)
- `_count_nodes` (line 1147)

Python 默认递归深度限制 ~1000, 而 1000 个加法链的 AST 节点深度直接超出。

**影响**:
- 任何深度嵌套的 Python 表达式 (1+1+... * 1000) 都触发栈溢出
- 用户实际场景: 数据处理脚本/生成代码/嵌套表达式均可能触发
- 5 个 walk 函数均受影响, 不止一个

## 决策

### 决策 1: 迭代化 (用栈替代递归) - 5 个函数全部修复

**统一模式**:
```python
stack: list[_TreeNode] = [node]
while stack:
    current = stack.pop()
    # 处理 current
    stack.extend(reversed(current.children))  # reversed 保 depth-first 顺序
```

**为什么 reversed**:
- 原始 `for child in node.children:` 是**正向**遍历
- `stack.pop()` 是**LIFO**, 反向 push children 才能保持正向遍历顺序
- 行为与原递归一致 (depth-first, 顺序 children)

### 决策 2: 保留原 `_walk_imports` 跳过逻辑

`_walk_imports` 内部有 `if node.type in ("import_statement", "import_from_statement"): continue` 守卫 (不递归进入已解析的 import)。迭代化时保留此守卫，避免误触发 `_parse_python_import` 重复解析。

### 决策 3: `_walk_functions` 保持原样

`_walk_functions` 是**单次 dispatch** (按 language 分派到 `_walk_*`), 不递归。它**调用** `_walk_python_functions` 但本身不递归。其深度 = 1 + child walk 深度, 已通过 child 修复解决。

### 决策 4: 测试覆盖 4 类别

`tests/test_ast_parser_recursion.py`:
- 4 个 chain 边界 (100/500/1000/2000 加法链)
- 50 层嵌套 class
- 50 层嵌套 function
- 3 个原有边界 (空文件/Unicode/10K 行) 回归

## 后果

### 正面
- **5 个 walk 函数全部迭代化**——深度 AST 不再触发 RecursionError
- 9 个新测试覆盖深度 AST + 边界场景
- 209 个相关测试全过 (无回归)
- 性能: 迭代化用 list (非 deque), 对小 AST 无显著影响

### 负面
- 行为与原递归**逻辑等价**, 但**遍历顺序细节**依赖 `reversed(children)` 的栈管理, 需保留此不变式
- 大量代码改动 (5 个函数), 风险面较广; 但都有对应测试覆盖

## 验证

- 9/9 `test_ast_parser_recursion.py` 通过
- 209/209 相关测试通过 (ast_parser / semantic_rules / semantic_checker / phase2_5)
- quality-gate: 192 passed, 0 failed
- baseline: 19 (12 文件) 一致
- typecheck: 192 source files 无问题
- lint: All checks passed

## 累计状态

- 48+1=49 ADR (含本 ADR)
- 11 降级规则 (baseline.json)
- 3919+9=3928 tests passed
- 88.03% 总覆盖率 (稳定)
- 深度 AST 安全性提升: 1000 → 2000+ 加法链安全
- ADR-041/045/046/047 修复后, 进一步消除 ast_parser 隐含栈溢出风险