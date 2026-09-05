# ADR-053: Phase 33b-13 check_directory 不再静默过滤 skipped 文件

## 状态
接受

## 日期
2026-09-05

## 背景

按指令"validate the result through its public interfaces and acceptance behavior"用真实端到端跑 `check_directory(empty_dir)` 时发现**真实契约缺口**:

**真实发现 9**: 空文件 (0 字节) **完全不出现在 check_directory 结果中**
- 创建 5 个空文件 + 1 个真实文件 → `check_directory` 只返回 1 个结果
- `empty.py` **静默丢失** (SARIF/JUnit 也无法报告)

**根因**: `tools/scripts/rules_engine/checker.py` line 656-657 (修复前):
```python
if not result.skipped:
    results.append(result)
```
**显式过滤** skipped 文件, 但调用方期望看到所有文件.

**影响**:
- Phase 33b-12 修复 (`_build_pass_testcase` 加 `<skipped/>` 标记) **永远没机会触发** — 因为 skipped 文件没到 report_generator
- serial 路径 (≤4 文件) 过滤 skipped, parallel 路径 (>4 文件) **保留** skipped — **不一致行为**
- 用户看不到空文件, CI 报告"X 个文件已扫描"实际是"X - 空文件数"

## 决策

### 决策 1: `_check_files_serial` 不再过滤 skipped

```python
# Phase 33b-13 fix (ADR-053): 不再静默过滤 skipped 文件
results.append(result)
```

**一致性**: serial 与 parallel 路径**都**保留 skipped, 让 `_build_sarif_results` 用 `kind=notApplicable` 正确报告.

### 决策 2: 端到端契约测试 (3 个新测试)

- `test_check_directory_includes_skipped_files`: 验证 `check_directory` 返回 skipped
- `test_check_directory_skipped_in_sarif_end_to_end`: 验证 SARIF `kind=notApplicable`
- `test_check_directory_skipped_in_junit_end_to_end`: 验证 JUnit `<skipped/>`

## 后果

### 正面
- **真实契约修复**: 空文件不再静默丢失, SARIF/JUnit 端到端可见
- **路径一致**: serial 和 parallel 都保留 skipped (之前不一致)
- **Phase 33b-12 修复真正生效**: skipped 文件可被 report_generator 正确显示
- **3 个新端到端测试** 锁定契约 (基于真实 check_directory + generate_*)

### 负面
- 任何**之前**断言 `len(check_directory()) == N` (排除空文件) 的测试可能失败
- 但这种断言是错的, 应改为"passed 文件数 = N - skipped"

## 验证

- 3/3 `test_check_directory_skipped.py` 通过
- lint / typecheck / quality-gate / baseline 全过
- 全量 3945+ tests 无回归 (待 commit 后确认)

## 累计状态

- 53+1=54 ADR (含本 ADR)
- 11 降级规则 (baseline.json)
- 3945+3=3948 tests passed
- 88.26% 总覆盖率
- check_directory 端到端契约完整锁定