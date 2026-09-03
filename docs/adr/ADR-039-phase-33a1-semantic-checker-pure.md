# ADR-039: Phase 33 子任务 33a-1 semantic_checker 纯函数覆盖

## 状态
接受

## 日期
2026-09-03

## 背景

按 ADR-036 启动 Phase 33 子任务 33a-1: 覆盖 `semantic_checker.py` 纯函数。
semantic_checker.py 共 221 行, 73% 覆盖率, 含 3 个纯函数:
- `_check_from_import` (10 行, 简单)
- `_check_module_import` (13 行, 简单)
- `ImportGraph.add_edge` (6 行, 最简单)

## 决策

### 决策 1: 测试用 dataclass factory (make_import)

```python
def make_import(module="os", names=None, line=1, is_from=False, level=0) -> ImportInfo:
    return ImportInfo(module=module, names=names or [], line=line, is_from=is_from, level=level)
```

理由: ImportInfo 是 frozen dataclass, 测试中重复构造繁琐。Factory 函数集中默认值, 减少噪音。

### 决策 2: 覆盖 4 个核心分支 (3 函数 × 4 测试 = 12 测试)

- `_check_from_import` (4): unused / used / empty_names / mixed
- `_check_module_import` (4): unused / used / empty_module / nested (短名检查)
- `ImportGraph.add_edge` (4): basic / bidirectional / duplicate (set 去重) / chained

## 后果

### 正面
- 12 个测试覆盖 3 个纯函数所有关键分支
- 测试反映真实行为, 不依赖 mock
- 估时 5 min → 实测 5 min, 完全符合 ADR-030 计划

### 负面
- 仍有 78% 未覆盖 (semantic_checker.py 整体 73% → 78% 估时, 后续 33a-2/3/4 推进)
- dataclass Factory 不是 idiom 标准 (但 简单清晰)

## 验证

- pytest: 12/12 passed in 1.19s
- ruff: 待检查
- 覆盖率: semantic_checker.py 73% → 估时 78% (待实测)

## 后续

- Phase 33 子任务 33a-2: 私有 cache 函数 (估时 1h)
- Phase 33 子任务 33a-3: 公开 API 集成 (估时 1h)
- Phase 33 子任务 33a-4: LRU/snapshot (估时 1h)