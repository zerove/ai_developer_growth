# ADR-036: Phase 33 启动规划 - semantic_checker/semantic_rules 补测

## 状态
接受 (规划,未启动)

## 日期
2026-09-03

## 背景

Phase 32 完整收口 (commit: c06ae70 / dc5ee10) 后, 4 个原 <80% 模块中 2 个已突破门禁:
- ✅ regex_cache.py: 100% (ADR-028)
- ✅ rule_loader.py: 81.28% (ADR-031~035)
- ⏸ semantic_checker.py: 73% (未补测)
- ⏸ semantic_rules.py: 72% (未补测)

本 ADR 规划 Phase 33 子任务, 后续会话可按 2e 的子任务分解模式逐步推进。

## 决策

### 决策 1: Phase 33 估时保守

| 文件 | 当前 | 估时 | 估时终态 |
|------|------|------|----------|
| semantic_checker.py | 73% | 1-2 天 | 95%+ |
| semantic_rules.py | 72% | 1-2 天 | 95%+ |

总估时: 2-4 天(分多次会话)

### 决策 2: Phase 33 子任务分解 (按 Phase 32 模式)

```
Phase 33a semantic_checker.py
- 33a-1 纯函数 (AST 节点分类) (5 min)
- 33a-2 私有 cache 函数 (1h)
- 33a-3 公开 API 集成 (1h)
- 33a-4 LRU/snapshot (1h)

Phase 33b semantic_rules.py
- 33b-1 纯函数 (rule 注册/查找) (5 min)
- 33b-2 私有 rule eval (1h)
- 33b-3 公开 API (1h)
- 33b-4 集成测试 (1h)
```

### 决策 3: 测试设计原则 (复用 Phase 32 沉淀)

- 模块级常量用 monkeypatch (ADR-032 模式)
- LRU cache 用 autouse fixture 清空 (ADR-033 模式)
- mock 模块属性而非导入路径 (ADR-033 关键陷阱)
- 测试反映真实行为 (不修复源码) (ADR-034 教训)
- 估算 API 时先 grep 实际函数名 (ADR-035 教训)

### 决策 4: 不在本次会话启动

session 已 40 commit / 36+ 小时连续工作, 不再延伸。
后续会话按 Phase 33a-1 启动 (纯函数, 5 min, 立即可做)。

## 后果

### 正面
- Phase 33 计划清晰, 后续会话可无缝衔接
- 测试设计原则已沉淀 (避免重蹈覆辙)
- ADR-029/030/032/033/034/035 提供完整 Phase 32 经验

### 负面
- 估时 2-4 天, 需多个会话
- 总覆盖率从 86.67% 提升到 ~89% (semantic_* 补测后)
- semantic 模块可能涉及复杂依赖 (AST 解析), mock 设计挑战

## 验证

- 计划完整: 4 个 33a 子任务 + 4 个 33b 子任务
- 测试原则 4 条: monkeypatch / LRU clear / 模块属性 / 真实行为
- ADR-029/030 经验复用

## 后续

下次会话启动 33a-1 (semantic_checker.py 纯函数, 估时 5 min)。
完成后 commit + 启动 33a-2, 持续推进。

## 累计状态

- 41 ADR (含本 ADR)
- 17 降级规则
- 3771 tests passed
- 86.67% 总覆盖率
- Phase 32 完整收口 ✅
- Phase 33 规划中
