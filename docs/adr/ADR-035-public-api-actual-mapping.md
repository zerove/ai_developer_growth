# ADR-035: Phase 32 子任务 2e 实际公开 API 调研

## 状态
接受

## 日期
2026-09-03

## 背景

按 ADR-030 启动 Phase 32 子任务 2e: 覆盖 `load_language_rules` + `load_combined_rules` + `invalidate_rule_cache` + `clear_rule_cache`。
**实际查证发现**: 这 4 个函数**不存在**于 `tools/scripts/rules_engine/rule_loader.py`。

## 决策

### 决策 1: 调整目标为实际公开 API

实际公开 API:
- `load_rules(language, framework_dir=None)` (line 250) - 主入口,带 LRU 缓存
- `load_custom_rules(project_dir)` (line 287) - 加载自定义规则 (3 源合并)
- `load_rules_for_language(language, framework_dir=None)` (line 440) - 实际就是 load_rules 的别名
- `load_domain_rules(project_path, framework_dir=None)` (line 486) - 域规则加载
- `_load_single_custom_file(rule_file, custom)` (line 318) - 内部 helper

### 决策 2: 无 `invalidate_rule_cache` / `clear_rule_cache`

`_RULE_CACHE` 是模块级 dict, **无公开清理 API**。
外部代码需 `rule_loader._RULE_CACHE.clear()` 直接访问 (破坏封装)。

**决策**: 不在 Phase 32 范围修复 (API 设计问题), 记录到 Phase 33 refactor 候选。

### 决策 3: 测试覆盖实际公开 API

预计 20-25 测试:
- `load_rules` (6-8): cache hit/miss/disk cache hit/generated rules/合并
- `load_custom_rules` (5-7): 3 源合并/global/project/legacy
- `_load_single_custom_file` (3-4): yaml 加载 + 合并
- `load_rules_for_language` (2): 别名 + framework_dir 传递
- `load_domain_rules` (3-4): domain 发现 + 加载 + 空

## 后果

### 正面
- 诚实修正 ADR-030 错误假设
- 覆盖**真实**公开 API
- 暴露 `_RULE_CACHE` 无清理 API 的设计问题

### 负面
- ADR-030 估时需重新评估 (实际函数比预期少 + 简单)
- 公开 API 缺口待 Phase 33 处理

## 验证

- 实测文件 line 250+ / 287+ / 440+ / 486+ 确认 4 个函数
- 检索 `invalidate` / `clear` 在 rule_loader.py 中**无匹配**

## 后续

- Phase 32 子任务 2e 实施 (按本 ADR 调整后的目标)
- Phase 33 refactor: 添加 `invalidate_rule_cache` / `clear_rule_cache` 公开 API
