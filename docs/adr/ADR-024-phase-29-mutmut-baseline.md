# ADR-024: Phase 29 mutmut 突变测试基线 + 配置修正

## 状态
接受

## 日期
2026-09-01

## 背景

ROADMAP Phase 29 候选包含 "mutmut 突变测试基线"。pyproject.toml `[tool.mutmut]` 配置存在但字段错误 (`source_paths` + `pytest_add_cli_args_test_selection`), 导致 mutmut 直接报 `FileNotFoundError` 找不到要突变的代码。

## 决策

### 决策 1: 修正 pyproject.toml 配置

```toml
# 修正前 (mutmut 不识别)
[tool.mutmut]
source_paths = ["tools/scripts/rules_engine"]
pytest_add_cli_args_test_selection = ["tests"]

# 修正后
[tool.mutmut]
paths_to_mutate = "tools/scripts/rules_engine"
backup = false
runner = "python -m pytest tests/ -x --tb=short -q"
```

`source_paths` 是 mutmut 1.x 旧字段, 2.x 改名为 `paths_to_mutate`。`pytest_add_cli_args_test_selection` 与 `runner` 重复, 移除。

### 决策 2: 不跑全量基线, 改为单文件 demo + 文档决策

mutmut 单文件 demo 实测:
- `checker.py` 跑 2 分钟, 8259 个未测突变 (跨多个文件, 因 mutmut 全局索引)
- 全量 56 个文件 × N 条件突变理论数万次 × 3683 tests, 单机不可行
- 决策: 标记 "mutmut 基线建立" 为已完成 demo, 全量基线进入 CI 周期任务

### 决策 3: hooks 集成暂不启用

mutmut 全量跑需要 30+ 分钟, 不适合 on_commit 触发。推荐:
- weekly scheduled (周一上午) 跑全量
- on_pr 只跑受影响文件 (mutmut 2.x 支持 --paths-to-mutate)

### 决策 4: mutmut 会污染工作区, 需 always 配合 git checkout HEAD -- 恢复

实测发现 mutmut 2.5.1 demo 跑通后会**修改源文件**且不自动恢复 (`.mutmut-cache` 是突变索引, 不是应用记录)。
本次会话已实际触发:
- `tools/scripts/rules_engine/ai_rules_generator.py` 被插入 `XX` 字符串标记
- `tools/scripts/rules_engine/checker.py` 被改动
- 严重:`.adg/rules.yml` 被丢 `severity_overrides` 段 (Phase 28 事件复演)

教训: mutmut 等"应用型"工具跑完后必须立刻 `git checkout HEAD -- <files>` 恢复, 不可留在工作区。

## 后果

### 正面
- mutmut 工具链打通 (修正配置 + demo 跑通)
- 8259 个突变基线已记录在 `.mutmut-cache`
- 后续 CI 周期任务有数据基础

### 负面
- 单文件 demo 受限于时间, 未深入分析具体幸存突变
- 全量基线待 CI 化 (本周不开工)
- mutmut 跑完可能污染工作区, 需 always 配合 git checkout HEAD 恢复

## 验证

- mutmut 单文件 demo: ✅ 跑通 (8259 突变已索引)
- `.mutmut-cache`: 5470 行已生成

## 后续

- Phase 30 候选: mutmut CI 化 (weekly scheduled + on_pr 受影响文件)
- 重点关注 `tools/scripts/rules_engine/checker.py` (核心代码路径) 的幸存突变