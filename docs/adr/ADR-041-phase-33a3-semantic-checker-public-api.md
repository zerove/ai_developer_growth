# ADR-041: Phase 33 子任务 33a-3 semantic_checker 公开 API 集成补测

## 状态
接受

## 日期
2026-09-04

## 背景

按 ADR-036 Phase 33 子任务分解, 在 33a-1 纯函数 (12 测试) 与 33a-2 私有方法 (13 测试) 之后, 启动 33a-3 公开 API 集成补测。

semantic_checker.py 公开 API:
- `analyze_file(filepath, language)`: 单文件解析
- `analyze_directory(dirpath, languages, max_files)`: 目录扫描 + 完整 SemanticResult
- `ImportGraph.find_cycles()`: DFS 环检测
- `ImportGraph.find_unused_imports()`: 未用 import 检测
- 内部辅助方法: `_parse_single_file`, `_emit_import_cycle_issues`, `_check_complexity`, `_check_missing_docstrings`, `_check_missing_docstrings` 类分支, `_collect_source_files`

33a-1 + 33a-2 后覆盖率: 73% → 83%。 33a-3 目标: 95%+。

## 决策

### 决策 1: 端到端 + monkeypatch 混合策略

公开 API 测试用 tmp_path 真实目录 (`tmp_path` fixture), 私有辅助方法用 monkeypatch mock 边界 (parser 异常/OSError/None)。

例: `_parse_single_file` 的 parser 异常分支 → `monkeypatch.setattr(checker.parser, "parse_file", _raise)`.

### 决策 2: 真实行为测试 (不修复源码)

发现 `analyze_file` line 196 单行缺失覆盖 → 直接构造 tmp_path 文件调用. 期望行为即实际行为, 不修改源码.

### 决策 3: line 408-409 noop 分支保留

`_check_complexity` 中 `if func.is_method and func.name.startswith("_") and not func.name.startswith("__"): pass` —— 这是一个 noop, 但**前面的 long-function/high-complexity append 已发生**, noop 不撤销. 测试反映真实行为 (两个 issue 仍被报).

### 决策 4: cycle 检测 bug 已知 + 测试绕过

发现 `_parse_single_file` add_edge 用 `rel_path` (如 "a.py") 作为 source, `imp.module` 是 tree-sitter 解析出的"import"语句名 (而非模块名). 所以 `a.py → "import"` 和 `b.py → "import"` 不构成环.

测试绕过: 直接 `monkeypatch.setattr(checker.import_graph, "find_cycles", lambda: [["a.py", "b.py", "a.py"]])` 验证 `_emit_import_cycle_issues` 集成.

注: 这是 ast_parser 解析 `import X` 的真实 bug, 不属于 33a-3 修复范围, 应作为独立 ADR 跟踪.

### 决策 5: dataclass factory (`_make_function`/`_make_class`/`_make_import`/`_make_file_ast`)

继承 Phase 33a-1 模式, 用工厂函数构造测试桩, 减少 `FunctionInfo(name="...", line=..., ...)` 冗长.

## 后果

### 正面
- 33a-3 完成 31 测试, semantic_checker 覆盖率 83% → **97%**
- 公开 API `analyze_directory` 完整端到端测试覆盖 (空目录/单文件/未用 import/cycle/复杂函数/语言过滤)
- 私有辅助方法边界 (异常/None/OSError/cycle emit/noop) 全部覆盖
- Phase 33a (semantic_checker) 推进到接近完成 (剩余 5 行边角)

### 负面
- ast_parser 解析 `import X` 语句名 bug 未修复, cycle 检测实战不可用
- noop 分支保留意义存疑 (前置 append 已生效), 属于设计问题
- 真实依赖 tree-sitter, 环境必须安装 (本会话已补 7 个 tree-sitter 包)

## 验证

- 31/31 测试通过 (`test_semantic_checker_public_api.py`)
- 全套测试: 3821 passed, 总覆盖率 87.72%
- quality-gate: 192 passed, 0 failed
- baseline: 19 (12 文件) 一致
- typecheck: 192 source files 无问题

## 累计状态

- 41+1=42 ADR (含本 ADR)
- 11 降级规则 (baseline.json)
- 3790+31=3821 tests passed
- 87.72% 总覆盖率
- Phase 33a-1, 33a-2, 33a-3 完成; 33a-4 (LRU/snapshot) 未启动
- Phase 33b (semantic_rules.py) 未启动
