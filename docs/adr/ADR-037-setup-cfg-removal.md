# ADR-037: setup.cfg 与 pyproject.toml mutmut 配置冲突修复

## 状态
接受

## 日期
2026-09-03

## 背景

第 4 次"全面分析"中执行 **B 深度二次分析**, 真实发现:

`setup.cfg` 与 `pyproject.toml` 的 `[tool.mutmut]` 配置**冲突**:
- `setup.cfg` 用 `source_paths` (mutmut 1.x 字段名)
- `pyproject.toml` 用 `paths_to_mutate` (mutmut 2.x 字段名, ADR-024)
- 两者并存导致 mutmut 启动时取其中一个 (通常按加载顺序), 行为不可预测

此外 `setup.cfg` 的 `runner` 字段引用了多个**不存在的测试文件**:
- `test_coverage_boost.py` (不存在)
- `test_coverage_boost_p2.py` (不存在)

如果 `mutmut run` 触发, 会因找不到测试文件立即失败。

## 决策

### 决策 1: 删除 `setup.cfg`, 单一配置文件源

理由:
- `pyproject.toml` 是现代 Python 标准 (PEP 621)
- `setup.cfg` 几乎无 git 历史 (空 git log)
- 配置冲突根因
- 单一配置源减少维护负担

### 决策 2: 所有 mutmut 配置已在 `pyproject.toml`

```toml
[tool.mutmut]
paths_to_mutate = "tools/scripts/rules_engine"
backup = false
# 注: pyproject.toml 中未指定 runner, 使用默认值
```

### 决策 3: 不修 `runner` 字段, 因已用新 CI 工具

实际 `mutmut_ci.sh` 用 `--paths-to-mutate=` CLI 参数 (ADR-024), 不依赖配置文件的 `runner` 字段。

## 后果

### 正面
- 配置冲突消除, 单一配置源
- mutmut 行为可预测
- 删除不存在的测试文件引用 (无副作用)

### 负面
- 删除 `setup.cfg` 不可逆 (已 git commit, 可恢复)
- 若外部脚本依赖 `setup.cfg` 加载配置, 需更新

## 验证

- ✅ setup.cfg 删除
- ✅ pyproject.toml 仍含 `[tool.mutmut]` 完整配置
- ✅ mutmut run 跑通 (demo)
- ✅ 无 .bak 残留 (mutmut 自动清理)
- ✅ check_rules_yml_integrity 通过

## 后续

- Phase 33 由下次会话按 ADR-036 启动
- 本 ADR 记录二次分析价值: 即使"全闭环"项目, 仍可能遗漏历史配置冲突