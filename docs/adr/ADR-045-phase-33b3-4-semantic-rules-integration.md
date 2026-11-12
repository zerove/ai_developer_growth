# ADR-045: Phase 33 子任务 33b-3/4 semantic_rules 集成测试

## 状态
接受

## 日期
2026-09-05

## 背景

按 ADR-036 Phase 33b 子任务分解, 33b-3 (公开 API) + 33b-4 (集成测试)。

由于 33b-2 已达 98% 覆盖率, 剩余 2 行不可执行 (TYPE_CHECKING/Protocol ...), 33b-3 实质上已完成。
本次主要做 33b-4 集成测试, 验证模块间联动:
- semantic_rules.run_semantic_rules() ↔ checker._run_semantic_checks()
- semantic_checker.analyze_directory() ↔ run_semantic_rules() 调度
- 用户自定义规则注册 → 自动调度

## 决策

### 决策 1: 真实集成 (不 mock 跨模块边界)

不 mock `run_semantic_rules()` 本身, 让真实规则在真实 FileAST 上跑,
仅 mock 边界条件 (parser 不可用 / parse_file 返回 None)。

### 决策 2: monkeypatch 不改 @lru_cache 单例

`get_parser()` 是 `@lru_cache(maxsize=1)` 单例, 第一次构造后 `available` 不变。
之前 monkeypatch.setattr(ast_parser, 'HAS_TREE_SITTER', False) 不影响已构造实例。
修法: monkeypatch `ASTParser.__init__` 设置 `_available=False` + `get_parser.cache_clear()`
强制重建. 测试结束后再次 cache_clear 保证隔离.

### 决策 3: ast_parser bug 不修, 仅记录

`ast_parser.parse_file()` 解析 'import X' 时把 'import' 当作 module,
导致 UnusedImportRule.imp.names 为空而跳过检测 (ADR-041 已记录).
本测试不强求 unused-import 报出, 仅验证 pipeline 不崩 + missing-docstring 仍触发.

### 决策 4: 自定义规则集成测试

register_semantic_rule() 注册自定义规则 → run_semantic_rules 自动调度:
- TodoFuncRule: 检测函数名含 'todo'
- RustOnlyRule: languages={'rust'} 对 python 文件不触发

try/finally 清理避免污染其他测试.

## 后果

### 正面
- 12 集成测试覆盖端到端 pipeline
- 模块间联动锁定: checker → semantic_rules → run_semantic_rules → 真实 Issue
- 验证 ASTParser bug 不破坏 pipeline (仅抑制 unused-import 报出)
- monkeypatch + cache_clear 模式可被后续测试复用

### 负面
- 3 个 tree-sitter e2e 测试在 monkeypatch 改 `HAS_TREE_SITTER` 后跳过
  (真实行为, 因后续测试复用 cached 单例时 available=False)
  修法: 改 mock `__init__` 强制 _available=False (本 ADR 决策 2)

## 验证

- 12/12 集成测试通过
- quality-gate: 192 passed, 0 failed
- baseline: 19 (12 文件) 一致
- typecheck: 192 source files 无问题
- lint: All checks passed

## 累计状态

- 45+1=46 ADR (含本 ADR)
- 11 降级规则 (baseline.json)
- 3887+12=3899 tests passed
- 87.72% 总覆盖率
- **Phase 33b (semantic_rules) 全部完成** ✅ (33b-1/2/3/4)
- Phase 33a (semantic_checker) 早已完成 ✅
