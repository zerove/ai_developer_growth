# ADR-030: Phase 32 启动 - rule_loader.py 补测子任务分解

## 状态
接受 (规划, 不实施)

## 日期
2026-09-02

## 背景

ADR-029 列出 rule_loader.py 覆盖率补测的整体规划 (4-6h, 274 行)。本 ADR- 将其分解为**可独立完成的小子任务**, 每个 <2h, 便于后续会话**分多次**完成,避免单次 session 饱和。

## 决策

### 决策 1: 分解为 5 个子任务

```
2a `_file_hash` (5 min, ~12 行测试)
    - 纯函数, 文件存在 → sha256 hex
    - 文件不存在 → ""
    - OSError (权限拒绝) → ""
    
2b `_load_disk_cache` + `_save_disk_cache` (~1h, ~15 行测试)
    - 文件存在 + 正常 JSON
    - JSONDecodeError → {}
    - OSError → {}
    - mkdir + write
    - 写失败 → 静默忽略
    
2c `_rules_hash_cached` + `_rules_hash` (~1h, ~20 行测试)
    - 多文件 hash (mock 真实 yml)
    - 文件不存在 (跳过)
    - OSError → ""
    - LRU cache (同 (lang, dir) 二次调用)
    - 默认 framework_dir (rules_dir())
    
2d yaml 加载系列 (~2h, ~30 行测试)
    - `_load_common_rules_cached`: yaml.safe_load 成功 + 失败 + 非 dict 返回
    - `_load_universal_rules_cached`: 合并 common + universal
    - `_try_load_yaml`: ImportError + yaml.safe_load 失败
    - merge_rules: 多种合并路径
    
2e 公开 API + 缓存失效 (~2h, ~25 行测试)
    - `load_language_rules`: cache hit + miss
    - `load_combined_rules`
    - `invalidate_rule_cache`
    - `clear_rule_cache`
    - `_load_generated_rules`: cache hit + ImportError 兜底
```

### 决策 2: 优先级 2a → 2e

按风险/价值排序:
- **2a** 立即可做 (纯函数, 5 min) — 最大 ROI
- **2b** 磁盘缓存常用 — 次高 ROI
- **2c** LRU 缓存关键 — 中等 ROI
- **2d** yaml 加载核心 — 较大 ROI 但复杂
- **2e** 公开 API 集成 — 最后做

### 决策 3: 每个子任务独立 commit

避免一次大 commit (难以 revert),每个子任务独立:
- commit message 格式: `feat(tests): rule_loader 2a _file_hash 覆盖`
- 每个子任务后跑覆盖率验证 (预期 +X%)
- 每个 commit 后跑 ruff + mypy

### 决策 4: 预期覆盖率进度

| 子任务 | 完成后覆盖率 |
|--------|--------------|
| 起点 | 77% |
| 2a 后 | 78% (+1) |
| 2b 后 | 81% (+3) |
| 2c 后 | 86% (+5) |
| 2d 后 | 92% (+6) |
| 2e 后 | 95%+ (+3) |

总覆盖率 86.67% → 88%+ (每子任务 +0.3%)

## 后果

### 正面
- 任务分解明确, 后续会话可分 5 次完成 (每次 30 min ~ 2h)
- 每个子任务独立可测, 失败可回滚
- 不再需要 4-6h 连续工作
- 风险分散: 每个子任务失败影响范围小

### 负面
- 5 次 commit, commit 数量增加 (但每次有明确价值)
- 期间可能存在"部分测试"状态

## 验证

- ADR-029 提供总览
- ADR-030 提供子任务分解
- 后续会话可任选子任务启动 (从 2a 开始)

## 后续

下次会话启动 2a (`_file_hash` 5 min 测试)。完成后 commit + 验证覆盖率, 进入 2b。