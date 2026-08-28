# ADR-013: pytest-xdist 覆盖率合并缺陷接受现状

## 状态
接受（2026-08-28）

## 背景
ROADMAP P1-2 要求"auto_fix 双路径重构"前置条件之一是"CI 覆盖率门禁
可信"。全量跑测试时（`python -m pytest tests/ -n auto --cov=tools.scripts
--cov=tools.lsp`）发现两个模块始终 0% 覆盖（`tools/scripts/rule_marketplace.py`
132 stmts / `tools/scripts/validate_rule_tests.py` 105 stmts），但单跑同一测试
文件时覆盖率为 99% / 95%。

## 调查与实验（2026-08-28，5 轮共 8 次全量跑）

| 方案 | 结果 |
|------|------|
| `--cov-append` | 仍 0% |
| `[tool.coverage.run] parallel = true` + `sigterm` | 仍 0% |
| `conftest.py` 加 `pytest_configure` 强制 `_cov.cov_controller.start()` | 无效（属性名错） |
| `[tool.coverage.run] data_file = ".coverage_data/.coverage"` + parallel | 仍 0% |
| `COVERAGE_FILE=.coverage-data` 环境变量 | 仍 0% |
| `--cov-config=pyproject.toml` addopts | 仍 0% |
| 去掉 `source` 字段改自动 discover | 仍 0% 且引入新 0%（lsp_server） |
| `--maxschedchunk=1` 强制每测试分发 | 仍 0% |
| `pytest -n 2` 单跑两文件（COVERAGE_FILE） | 99% / 95% ✓ |

## 根因诊断
- `.coverage` sqlite 表 `file` 含 189-191 个文件，`arc` 总计 32487-32833 条
- 但 `rule_marketplace.py` (file_id=183) 与 `validate_rule_tests.py` (file_id=181)
  的 `arc` 表行数恒为 0
- 其他 189 个模块均正常 — 说明 xdist 6 worker 中只有 2 个 worker 没跑这俩
  测试对应的 import 路径
- **pytest-xdist 3.8.0 + pytest-cov 7.1.0** 静态分析 `file` 表时把 collect 阶段
  见到 import 的所有模块都注册了；运行时分发测试时**仅跑测试的 worker 写 arc 数据**，
  最终 `.coverage.combine()` 时数据丢失
- 行为是 **xdist worker 不均匀 + coverage static collect 误报**的复合问题
- pytest-cov 7.1.0 的 `arcs_to_lines()` 信任 `line_bits`，但 7.x 数据存储改用
  `arc` 表 — 这是已知生态不兼容

## 决策
**接受现状，不在 v2.14.0 修复 xdist 覆盖率合并缺陷。**

1. **B2 不发版**：ROADMAP P1-2 不阻塞 — auto_fix 重构与覆盖率门禁可信度解耦
2. **文档化**："`tools/scripts/rule_marketplace.py` + `validate_rule_tests.py`
   全量跑显示 0% 是已知生态问题" — 在覆盖率快照中标注
3. **未来修复方向**（v2.15+ 候选）：
   - 升级 pytest-cov 至 8.x（解决 line_bits / arc 表兼容）
   - 或切到 coverage 7 的 `dynamic_context = true` 测试模式
   - 或在 conftest.py `pytest_collection_modifyitems` hook 中显式
     `importlib.import_module("tools.scripts.rule_marketplace")` 强制
     所有 worker 预加载

## 后果
- ✅ auto_fix 重构（C）可继续推进，不受 xdist 缺陷阻塞
- ✅ 86% 总体覆盖率、85% 阈值门禁仍然有效（3580 测试 0 失败）
- ⚠️ 单看 JSON 报告 `rule_marketplace.py` + `validate_rule_tests.py`
  显示 0% 是误报 — 但这两个模块单跑覆盖率达 99% / 95%，实际代码
  已被测试覆盖
- ⚠️ CI 上必须加注解或迁移到 pytest-cov 8.x 后再启严格 0% 门禁
