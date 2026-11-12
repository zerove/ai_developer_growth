# ADR-052: Phase 33b-12 report_generator skipped 文件契约修复

## 状态
接受

## 日期
2026-09-05

## 背景

按指令"validate the result through its public interfaces and acceptance behavior"用真实 `check_file` + `generate_*` 端到端时发现**真实公共契约缺口**:

**3 个发现**:
1. **SARIF**: skipped 文件**完全不在 SARIF 中** (112 results 全是有 issues 的; skipped 文件 0 个)
2. **JUnit XML**: skipped 文件出现为**空 testcase** (无内容, 无 `<skipped/>` 标记)
3. **统计错误**: `failures` 计数包含 skipped (实际应排除), `passed_count` 同理

**根因**:
- `_build_sarif_results` 只遍历 `result.issues`, 忽略 `result.skipped`
- `_build_pass_testcase` 不区分 passed vs skipped
- `_count_summary_stats` 和 `_count_html_summary` 用 `r.passed` 但 skipped 时 passed=True (因为 error_count=0)

**影响**:
- CI 工具 (GitHub Code Scanning 等) **看不到哪些文件被跳过**
- HTML 报告错误显示 skipped 为 passed, 误导用户
- 真实用户可能用 SARIF 验证文件列表, 漏文件 = 不可信

## 决策

### 决策 1: SARIF skipped 文件用 notApplicable 标记

```python
if getattr(result, "skipped", False) and not result.issues:
    runs_results.append(
        {
            "ruleId": "file-skipped",
            "level": "none",
            "message": {"text": "File skipped (empty or unsupported)"},
            "locations": [...],
            "properties": {"kind": "notApplicable"},
        }
    )
```

SARIF 标准: `kind: notApplicable` 表示该文件不适用, `level: none` 不算告警级别.

### 决策 2: JUnit skipped 文件用 `<skipped/>` 标记

```python
if getattr(result, "skipped", False):
    return [f"{testcase}<skipped/></testcase>"]
```

JUnit 标准: `<skipped/>` 是 JUnit 4+ 的标准 skipped 标记.

### 决策 3: failures / passed_count 排除 skipped

```python
failures = sum(1 for r in results if not r.passed and not getattr(r, "skipped", False))
summary["passed_count"] = sum(1 for r in results if r.passed and not getattr(r, "skipped", False))
summary["skipped_count"] = sum(1 for r in results if getattr(r, "skipped", False))
```

### 决策 4: JSON summary passed 排除 skipped

```python
non_skipped = [r for r in results if not getattr(r, 'skipped', False)]
"passed": all(r.passed for r in non_skipped) if non_skipped else True
```

空 results 或全 skipped → passed=True (无可失败).

### 决策 5: 向后兼容 - 用 getattr 默认 False

`ValidationResult` 类**没有** `skipped` 字段 (只有 `CheckResult` 有). 用 `getattr(r, 'skipped', False)` 默认 False 保证:
- 旧 ValidationResult 实例继续工作 (skipped=False)
- 新 CheckResult 实例正确识别 (skipped=True)
- 无需修改 21 个失败测试的数据类

## 后果

### 正面
- **SARIF 端到端契约修复**: skipped 文件以 `kind: notApplicable` 标记, 不再丢失
- **JUnit 端到端契约修复**: skipped 文件用 `<skipped/>` 标记
- **统计正确性**: failures / passed_count / JSON passed 排除 skipped
- **向后兼容**: 21 个旧测试通过 (getattr 默认 False)
- 6 个新端到端测试 (test_report_generator_skipped.py) 锁定契约

### 负面
- `CheckResult` dataclass 无 `skipped` 字段, 需 `getattr` 兼容 (但更显式)
- 统计逻辑略复杂 (额外 skipped 条件)

## 验证

- 6/6 `test_report_generator_skipped.py` 通过
- 104/104 旧相关测试通过 (test_validators_cli / test_report_and_fix / test_language_rules_v2)
- 3945/3945 全量测试通过
- quality-gate: 192 passed, 0 failed
- baseline: 19 (12 文件) 一致
- typecheck: 192 source files 无问题
- lint: All checks passed

## 累计状态

- 52+1=53 ADR (含本 ADR)
- 11 降级规则 (baseline.json)
- 3940+5+0=3945 tests passed (5 新 skipped 测试, 1 test 升级)
- 88.26% 总覆盖率 (+0.10%)
- 4 报告格式 + skipped 端到端契约完整锁定
