# ADR-015: pytest-xdist race condition 接受现状

## 状态
**Accepted** (2026-08-29)

## 背景
v2.14.0 全量测试 (`pytest tests/test_adg_cli_v2.py -n auto`) 偶发 2 个 fail，
单跑 (`pytest tests/test_adg_cli_v2.py`) 100/100 pass。

### 现象
- 失败测试: `test_fix_python_bare_except` 类下子用例（涉及 ruff subprocess 调用）
- 重跑立即 pass，无代码变更
- 覆盖率数据正常（19,431 stmts / 88.52%），不受影响

### 排查
1. 单跑无失败 → 排除代码逻辑 bug
2. 加 `pytest -p no:randomly` 仍有偶发 → 排除顺序敏感
3. 加 `pytest -n 0`（无并发）100% pass → 确认 xdist 引发
4. 失败集中在 ruff subprocess 调用 → 并发 + subprocess 资源竞争
5. `pytest-xdist 3.8.0` + `pytest-cov 7.1.0` 已知 issue:
   https://github.com/pytest-dev/pytest-cov/issues/610

### 根因
xdist worker 并行触发 ruff subprocess 时，临时目录 / 文件描述符
资源竞争 + pytest-cov 7.x 的 `.coverage` 文件并发写入冲突。

## 决策
**接受现状**，标记偶发失败为已知问题，不阻塞 v2.14.0 / v2.15.0 发版。

### 接受依据
1. **不影响 CI 门禁**: 全量测试在偶发失败时 `pytest --lf` 立即复绿
2. **不影响覆盖率数据**: 实测 88.52% 在单跑与并发跑下结果一致
3. **有清晰重跑路径**: `pytest --lf -n 0` 或 `pytest -p no:xdist`
4. **已记录 work-around**: CI 失败时可自动 `--lf` 重试一次
5. **升级到 pytest-cov 8.x 需独立验证**: 列入 v2.15+ 候选（ADR-013 同源）

### 缓解措施
- 本地开发: 用 `pytest -n 0` 或 `pytest tests/<single_file>.py`
- CI 流程: `pytest --lf` 重试一次（已配置）
- 文档: CONTRIBUTING.md 增 "并发测试已知问题" 段落

## 后果
- v2.15.0 仍可能偶发 2 fail
- 真正修复需 pytest-cov 8.x + xdist 3.6+ 完整验证（独立 task）
- 不影响"覆盖率 88.52%"基线报告

## 替代方案
| 方案 | 评估 | 决策 |
|---|---|---|
| 降级 xdist 到 2.x | 失去 3.x 的 `--maxschedchunk` 等 | 拒绝 |
| 移除 ruff subprocess 改纯 regex | 损失 ruff 真实修复能力 | 拒绝 |
| 升级 pytest-cov 8.x | 需独立验证，可能引入新 bug | 列入 v2.15+ 候选 |
| 用 `pytest.mark.flaky` 标记 | 掩盖问题不可接受 | 拒绝 |

## 参考
- ADR-013: pytest-xdist coverage 合并 bug 接受 (v2.13.17)
- pytest-cov issue #610
- v2.14.0 commit 81f3b58
