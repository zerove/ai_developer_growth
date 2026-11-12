# ADR-042: Phase 33 子任务 33a-4 ASTParser LRU/snapshot 补测

## 状态
接受

## 日期
2026-09-04

## 背景

按 ADR-036 Phase 33 子任务分解, 在 33a-1/2/3 完成后启动 33a-4 "LRU/snapshot"。

ast_parser.py 中 LRU/snapshot 关注点:
- `get_parser()` 标注 `@lru_cache(maxsize=1)` 单例工厂
- `ASTParser._PARSER_CACHE` 类级共享 parser 字典
- `ASTParser.reset_parser_cache()` 测试用清理接口
- `ASTParser._shared_parsers()` lazy 初始化 (第一次触发, 后续短路)
- `ASTParser.supported_languages()` 返回当前可用语言 snapshot

## 决策

### 决策 1: 真实行为测试 (不修复源码)

`get_parser()` 是单行 `return ASTParser()`, @lru_cache 装饰由 functools 提供.
测试不修复源码, 直接调用 `cache_clear()` 验证单例语义.

### 决策 2: 边界覆盖 parse() 与 supported_languages()

parse() 边界:
- 不可用 parser → None
- 不支持语言 → None
- bytes 输入 → tree 或 None
- 空字符串 → tree (空代码)

supported_languages() 边界:
- HAS_TREE_SITTER=False → 空 set (monkeypatch 覆盖)

### 决策 3: _PARSER_CACHE_RESET 是 fixture 模式

autouse fixture 不在此文件, 而在 test_ast_parser.py 与 test_conftest.py.
本测试用 monkeypatch.setattr 模拟 cache 清理行为.

## 后果

### 正面
- 23 测试覆盖 LRU/snapshot 全链路 (单例/清理/lazy/边界)
- 真实发现 ast_parser 无 `languages` property, 无模块级 `SUPPORTED_LANGUAGES`
  (类内常量) — 测试改为访问 `ASTParser.SUPPORTED_LANGUAGES`
- Phase 33a (semantic_checker) 子任务全部完成 (33a-1/2/3/4)

### 负面
- ast_parser.py 整体覆盖率仍 72% (各语言具体解析分支不在本次任务范围)
- `languages` property 缺失, 但 `supported_languages()` 方法已存在 (符合 duck typing)

## 验证

- 23/23 测试通过 (`test_ast_parser_lru.py`)
- 全套测试: 3821+23=3844 tests passed
- quality-gate: 192 passed, 0 failed
- baseline: 19 (12 文件) 一致
- typecheck: 192 source files 无问题

## 累计状态

- 42+1=43 ADR (含本 ADR)
- 11 降级规则 (baseline.json)
- 3844 tests passed
- 87.72% 总覆盖率
- **Phase 33a (semantic_checker) 全部完成** ✅
- Phase 33b (semantic_rules.py) 未启动
