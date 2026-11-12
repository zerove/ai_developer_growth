# ADR-033: Phase 32 子任务 2c rules_hash mock 设计

## 状态
接受

## 日期
2026-09-02

## 背景

按 ADR-030 启动 Phase 32 子任务 2c: 覆盖 `_rules_hash_cached` (LRU cache) + `_rules_hash` (公开 API)。
实施中遇到一个**真实 Python 陷阱**,值得记录。

## 决策

### 决策 1: mock 模块属性而非导入路径 (关键陷阱)

```python
# 反例: 看似正确但无效
from tools.scripts import _common

monkeypatch.setattr(_common, "rules_dir", lambda: tmp_path)  # ❌ 无效

# 正例: 必须 mock rule_loader.rules_dir
from tools.scripts.rules_engine import rule_loader

monkeypatch.setattr(rule_loader, "rules_dir", lambda: tmp_path)  # ✅ 有效
```

理由: rule_loader 顶部 `from tools.scripts._common import rules_dir` 在**导入时**绑定函数对象。后续 `rule_loader.rules_dir()` 调用的是**已绑定**的对象, 不会去 `_common.rules_dir` 查找。

这是 Python `from X import Y` 的标准行为 (形成独立绑定), 但常被 mock 用户忽视。

### 决策 2: 测试前清空 LRU cache (autouse fixture)

```python
@pytest.fixture(autouse=True)
def _clear_lru_cache():
    _rules_hash_cached.cache_clear()
    yield
    _rules_hash_cached.cache_clear()
```

理由: `_rules_hash_cached` 是 `@lru_cache`,跨测试会污染 (测试 A 的 cache 影响测试 B)。每次测试前后清空确保隔离。

### 决策 3: 覆盖 8 个分支 (而非 5 个)

原 ADR-030 估时 5 分支,实际实施 8 分支:
- `_rules_hash_cached`:
 - 多文件 hash (64 字符 hex) (1)
 - 两文件都缺失 → 空 hash (1)
 - 仅一个文件存在 → 跳过缺失 (1)
 - OSError → "" (root 跳过) (1)
 - LRU cache 命中 (1)
 - LRU cache miss (不同 args) (1)
- `_rules_hash`:
 - 默认 framework_dir (mock rules_dir) (1)
 - 显式 framework_dir (1)

## 后果

### 正面
- 8 个测试覆盖 _rules_hash 完整生命周期
- ADR-033 记录关键 Python 陷阱 (模块绑定 vs 导入路径 mock)
- mock 设计可复用到后续 2d (yaml 加载) + 2e (公开 API)

### 负面
- rule_loader.py 覆盖率 18% → 26% (估时 +8pp, 实测 +8pp)
- 仍有 74% 未覆盖, 待 2d/2e

## 验证

- pytest: 8/8 passed ✅
- ruff: clean ✅
- 覆盖率: rule_loader.py **26%** (子任务 2c 完成)
- 测试套件 3717 → 3725 (+8)

## 后续

- Phase 32 子任务 2d: yaml 加载 (`_load_common_rules_cached` + `_load_universal_rules_cached` + `_try_load_yaml`) (2h)
- Phase 32 子任务 2e: 公开 API (`load_language_rules` + `load_combined_rules` + invalidate/clear) (2h)
