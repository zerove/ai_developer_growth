# ADR-044: Phase 33 子任务 33b-2 semantic_rules rule eval 补测

## 状态
接受

## 日期
2026-09-05

## 背景

按 ADR-036 Phase 33b 子任务分解, 在 33b-1 纯函数覆盖后启动 33b-2 (rule eval)。

semantic_rules.py 三个内置规则的 check() 方法 + run_semantic_rules() 调度逻辑覆盖:
- UnusedImportRule.check() (28 行)
- MissingDocstringRule.check() (21 行)
- HighComplexityRule.check() (21 行)
- run_semantic_rules() (9 行)

33b-1 后覆盖率 41% (仅 pure 函数层). 33b-2 目标: 90%+.

## 决策

### 决策 1: 真实行为测试 + SimpleNamespace 桩对象

不修改源码, 直接用 `types.SimpleNamespace` 构造 duck-typed 测试桩
(imports/names/line/is_from/level + functions/name/line/docstring/complexity)。
这种 duck typing 与源码 `getattr(imp, 'names', [])` 模式一致。

### 决策 2: 异常隔离用 monkeypatch.setattr

run_semantic_rules 第 245-249 行 try/except 隔离单条规则失败:
- 不阻断其他规则 (P4 阶段沉淀)
- 测试用 `monkeypatch.setattr(MissingDocstringRule, 'check', _raise)` 模拟

### 决策 3: boundary 测试 (complexity=10 vs 11)

HighComplexityRule 阈值是 > 10 (即 11 触发):
- test_complexity_threshold_is_10: 边界测试确保阈值正确

### 决策 4: enabled_rules 过滤语义

run_semantic_rules 第 243 行 `enabled_rules is not None and rule.name not in enabled_rules`:
- enabled_rules=None → 全部运行
- enabled_rules={'unused-import'} → 仅 unused-import 运行

## 后果

### 正面
- 22 测试覆盖 rule eval 全栈 (3 个内置规则 check + run_semantic_rules 调度)
- semantic_rules.py 覆盖率 **72% → 98%** (剩余 2 行: TYPE_CHECKING 块 + Protocol ... 字面)
- 内置规则行为锁定 (UnusedImport/MissingDocstring/HighComplexity)
- 异常隔离模式验证, 与 P4 阶段沉淀一致

### 负面
- TrueDivergence: Phase 33b-3/4 已无大幅空间 (剩余 4 行不可覆盖)
- SimpleNamespace duck typing 不强制字段类型 (rubber duck)

## 验证

- 22/22 测试通过 (`test_semantic_rules_eval.py`)
- semantic_rules.py 覆盖率: 72% → **98%**
- quality-gate: 192 passed, 0 failed
- baseline: 19 (12 文件) 一致
- typecheck: 192 source files 无问题
- lint: All checks passed

## 累计状态

- 44+1=45 ADR (含本 ADR)
- 11 降级规则 (baseline.json)
- 3865+22=3887 tests passed
- 87.72% 总覆盖率
- **Phase 33b-1 + 33b-2 完成** ✅ (semantic_rules 覆盖率 72% → 98%)
- Phase 33b-3 (公开 API 集成) 未启动
- Phase 33b-4 (集成测试) 未启动