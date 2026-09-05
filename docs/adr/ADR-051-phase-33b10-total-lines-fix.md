# ADR-051: Phase 33b-10 ComplexityMetrics.total_lines 真实填充

## 状态
接受

## 日期
2026-09-05

## 背景

按指令"validate the result through its public interfaces and acceptance behavior"在真实项目代码 (`tools/scripts/rules_engine/`, `tools/scripts/`) 上跑 `SemanticChecker.analyze_directory` 端到端时, 发现:

```
tools/scripts/rules_engine/: 56 files, 0 lines
tools/scripts/ (192 files): 0 lines
```

`result.metrics.total_lines` 字段**总是 0**, 而其他字段（`total_functions`/`total_classes`/`total_imports`）正确。

**根因**:
- `ComplexityMetrics.total_lines: int = 0` 字段存在 (line 164)
- `FileAST` dataclass **没有** `total_lines` 字段
- `parse_file` 拆分 `lines = code.splitlines()` 后**丢弃**行数
- `_calculate_metrics` 累加循环**没**累加 `total_lines`

**实际契约缺口**:
- `test_semantic_checker.py:96` `assert metrics.total_lines == 0` 接受现状
- `test_semantic_checker_deep.py::test_calculate_metrics_with_data` **没**验证 `total_lines`
- 没有任何代码调用 `parse_file` 后获取行数（**潜在**下游使用)

**真实使用**:
- `analyze_directory` 是公共 API, 返回 `SemanticResult.metrics.total_lines`
- 下游可基于此字段做代码量统计/复杂度归一化

## 决策

### 决策 1: 三处修改

1. `ast_nodes.py::FileAST` 加 `total_lines: int = 0` 字段 (dataclass field, 默认 0)
2. `ast_parser.py::_build_code` 填充 `total_lines=len(lines)` (line 341)
3. `semantic_checker.py::_calculate_metrics` 累加 `metrics.total_lines += ast_result.total_lines` (line 459)

### 决策 2: 测试覆盖 (真实端到端)

`tests/test_semantic_checker_total_lines.py` 3 个测试:
- `test_total_lines_real_rules_engine`: 56 文件 → 期望 ≥ 500 行
- `test_total_lines_real_tools_scripts`: 192 文件 → 期望 ≥ 10000 行
- `test_total_lines_specific_file`: 临时 50 行文件 → 期望 `ast.total_lines == 50`

也升级 `test_calculate_metrics_with_data` 验证 `metrics.total_lines == 100` 累加逻辑。

## 后果

### 正面
- `ComplexityMetrics.total_lines` 字段从"恒为 0" 变为"真实可信"
- **真实结果**: 56 文件 → 13,946 行; 192 文件 → 48,868 行
- 3 个新端到端测试基于真实项目代码（不是合成 fixture）
- `_calculate_metrics` 累加逻辑测试覆盖

### 负面
- `FileAST` 加字段 → 旧代码构造 `FileAST(...)` 不传 `total_lines` 会用默认值 0（向后兼容）
- 任何依赖 `total_lines=0` 作为"无数据"信号的下游代码需调整

## 验证

- 3/3 `test_semantic_checker_total_lines.py` 通过
- 13/13 `test_semantic_checker_deep.py` 通过（含升级的 `test_calculate_metrics_with_data`）
- 真实端到端契约: `tools/scripts/rules_engine/` 56 files → **13,946 lines** ✅
- 全量门禁（lint/typecheck/quality-gate/baseline）全过

## 累计状态

- 51+1=52 ADR (含本 ADR)
- 11 降级规则 (baseline.json)
- 3936+3+1=3940 tests passed (3 新端到端 + 1 升级)
- 88.16% 总覆盖率
- `ComplexityMetrics` 真实可信: `total_lines` 字段从 0 → 实际值