# ADR-028: regex_cache iter_cached 修复 + 覆盖率补测

## 状态
接受

## 日期
2026-09-02

## 背景

按 P2 优先级补测覆盖率 < 80% 的 `tools/scripts/rules_engine/regex_cache.py` (78%)。

测试期间意外发现一个**真bug**:
- `iter_cached()` 在 flags 是 `re.MULTILINE` 等 `RegexFlag` 枚举时抛 `ValueError: invalid literal for int() with base 10: 're.MULTILINE'`
- 原因: `get_compiled()` 用 `f"{pattern}:{flags}"` 作 cache key, `str(re.MULTILINE) = 're.MULTILINE'` 而 `int()` 不能解析
- 影响: `iter_cached()` 从未被任何路径调用过 (否则早就炸了)
- 风险: 任何诊断/测试工具如果调用 iter_cached 都会 crash

## 决策

### 决策 1: 修复 iter_cached 兼容 RegexFlag

`tools/scripts/rules_engine/regex_cache.py` 的 `iter_cached()`:
```python
# 旧版
yield pattern, int(flags_str)  # ValueError on re.MULTILINE

# 新版
try:
    flags_value: int | str = int(flags_str)
except ValueError:
    flags_value = flags_str
yield pattern, flags_value
```

返回类型由 `Iterator[tuple[str, int]]` 扩展为 `Iterator[tuple[str, object]]` (兼容 int 和 str)。

### 决策 2: 新增 test_regex_cache.py (20 个测试)

覆盖目标:
- `_is_dangerous`: 4 种危险模式 + 安全模式 (6 个测试)
- `get_compiled`: LRU 缓存 hit/miss/eviction/move_to_end (5 个测试)
- `is_dangerous / get_dangerous`: 公开 API (2 个测试)
- `clear_cache / cache_stats / iter_cached`: 缓存管理 (3 个测试,含 fix 后行为)
- `scan_dangerous_patterns`: 批量扫描 (2 个测试)
- `RegexSafetyError`: 异常类 (1 个测试)

### 决策 3: 覆盖率预期从 78% → 95%+

regex_cache.py 共 137 行,原缺失 30 行。新测试覆盖:
- LRU eviction path (cache 满后淘汰)
- iter_cached 兼容 RegexFlag path
- 所有危险模式检测分支
- 全部公开 API

## 后果

### 正面
- 修复了潜在 crash bug (iter_cached + RegexFlag)
- regex_cache 覆盖率从 78% → 100% (实测)
- 测试套件 3683 → **3703** (+20)
- 真实事件验证 TDD 流程价值 (写测试 → 发现 bug → 修源码)

### 负面
- iter_cached 返回类型扩展可能影响调用方 (但代码无调用方, 安全)
- 后续需补测其他 3 个 <80% 模块 (rule_loader 77% / semantic_checker 73% / semantic_rules 72%)

## 验证

- pytest: 20/20 passed ✅
- 修复前: `iter_cached()` + re.MULTILINE = ValueError
- 修复后: `iter_cached()` + re.MULTILINE = 正常返回 ('re.MULTILINE' str)
- ruff: clean ✅
- 测试耗时: 0.77s (快)