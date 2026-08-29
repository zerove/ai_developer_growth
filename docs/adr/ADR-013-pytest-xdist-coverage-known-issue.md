# ADR-013 (修订): 覆盖率报告"假 0%" 现象

## 状态
**Revised** (2026-08-29) — 原 ADR 误判根因，正确结论见下方

## 原 ADR (v2.13.17) 描述
`rule_marketplace.py` + `validate_rule_tests.py` 在 `pytest --cov -n auto` 下显示 0%。
归因为 pytest-xdist 3.8.0 + pytest-cov 7.1.0 静态分析 file 表 vs arc 数据丢失。

## 复验 (v2.15.0)
直接跑对应测试：
```bash
pytest tests/test_rule_marketplace_v2.py tests/test_validate_rule_tests.py \
  --cov=tools.scripts.rule_marketplace \
  --cov=tools.scripts.validate_rule_tests \
  --cov-report=json
```
结果：**98.9%** + **95.1%** ✅ 全部达标。

## 真实根因
**不是 xdist/coverage bug**。是 `--cov` flag 范围 + 测试集选择问题：

1. 当跑 `pytest tests/test_adg_cli_v2.py -n auto --cov=tools.scripts` 时，
   `--cov` 范围包含整个 `tools.scripts.*`，但 **test_adg_cli_v2.py 不 import**
   `rule_marketplace` 或 `validate_rule_tests`。
2. 报告的 0% 是"该模块在本测试集内未被 import"，而非"模块本身无覆盖"。
3. xdist + coverage 都正常工作。

## 修正
- ADR-013 的"接受现状"改为"理解原理，无需修复"
- 不需升级 pytest-cov 8.x（不存在该版本，最高 7.1.0）
- 不需升级 pytest-xdist 3.6+（不存在，最高 3.8.0）
- coverage 库独立版本（已 7.15.4，正常）

## 实际改进建议
1. CI 跑全量 `pytest tests/` 避免选择偏差
2. 模块覆盖率只看"该模块专属测试集"或"全量测试"
3. `--cov=tools.scripts` 全范围跑必须包含全部 tests/

## 参考
- 实测数据: `.coverage-v215-target.json`
- pytest-cov PyPI: 最高 7.1.0
- pytest-xdist PyPI: 最高 3.8.0
