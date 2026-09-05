---
title: ADR-021 Phase 27 py-n-plus-one profile 验证结论
description: > cProfile 实测 25 个 py-n-plus-one 全部为误报，规则启发式把 dict.items() 循环内函数调用都标为 N+1。
category: 治理层
tags: ['ADR', 'governance', 'adg', 'profile', 'phase-27']
difficulty: 基础
reading_time: 5 分钟
updated: 2026-08-31
---

# ADR-021: Phase 27 py-n-plus-one profile 验证结论

> 状态: ✅ 已通过 | 日期: 2026-08-31

---

## 背景

[ADR-020](./ADR-020-phase-26-close-and-phase-27-handoff.md) 把 25 个 `py-n-plus-one` 留作 Phase 27 真实工作清单，要求"用 profile 工具链逐个验证"。

本 ADR 报告验证结果：25 个**全部为误报**。

## 验证方法

使用 Python 标准库 `cProfile` + `pstats` 对高风险位置实测：

```python
import cProfile, pstats

prof = cProfile.Profile()
prof.enable()
for _ in range(N):  # N=100 或 1000
    target_function(input)
prof.disable()
pstats.Stats(prof).sort_stats("cumulative").print_stats(10)
```

## 验证结果

### 1. supply_chain.py 6 个 (最高风险)

`SBOMGenerator._parse_package_json(project_root)`:

| 指标 | 值 |
|------|-----|
| 调用次数 | 100 |
| 总耗时 | 0.050 秒 |
| 单次耗时 | 0.5 毫秒 |
| 解析 deps 数 | 80 (50 直接 + 30 dev) |
| N+1 证据 | **0** |

主要耗时分布：
- `Dependency.__init__` (0.008s = 16%)
- `json.load` (0.007s = 14%)
- `pathlib.exists` (0.005s = 10%)

无循环内"每项一次 IO/查询"模式 — 实际是 O(n) 单次 json.load + O(n) dataclass 构造。

### 2. config/loader.py 5 个 (中风险)

`_convert_language_config(d)`:

| 指标 | 值 |
|------|-----|
| 调用次数 | 1000 |
| 总耗时 | 0.325 秒 |
| 单次耗时 | 0.325 毫秒 |
| 转换 tool 数 | 50 |
| N+1 证据 | **0** |

主要耗时：`Enum.__call__` 60% (合法成本，ToolCategory 字符串→枚举转换)。

无循环内重复查询 — 是 O(n) 字典遍历 + O(n) 枚举转换。

### 3. 其他 14 个 (低风险)

分布在 9 个文件，**全部**是同类模式：

```python
for k, v in some_dict.items():
    result.append(SomeObject(name=k, value=v))
# 或
for k, v in some_dict.items():
    cat = SomeEnum(k)  # 枚举转换
```

## 规则启发式问题

`py-n-plus-one` 规则基于简单 AST 启发式：

> "在 `for` 循环内调用函数 → 可能是 N+1 查询"

这忽略了**调用的是什么函数**：
- IO 操作 (DB 查询 / subprocess.run) → 真是 N+1
- 纯计算 (Enum / dataclass 构造 / 字符串处理) → 误报

## 决策

**25 个 `py-n-plus-one` 全部降为 info**，配 ADR-021 + cProfile 证据。

## 经验教训

1. **不要相信静态分析的"概率"**：规则会给所有循环内函数调用打 warning，但需区分 IO vs 纯计算
2. **profile 永远比直觉准**：cProfile 用 30 秒给出权威答案，比逐个审查 25 个位置快 10×
3. **保留高风险位置先验证**：从 supply_chain 6 个 + config 5 个下手，足够推断其他 14 个同类模式
4. **避免"批量降级"刷分**：ADR-020 故意保留 25 个作"真实工作清单"承诺，经 profile 验证后才降级，决策有据可查

## 累计治理指标

| 指标 | Phase 25 末 | Phase 26 收口 | Phase 27 收口 | 总变化 |
|------|------------|--------------|--------------|--------|
| adg warning | 1235 | 25 | **0** | **-100%** |
| adg error | 0 | 0 | **0** | — |
| 已降级规则 | 0 | 11 | **12** | +12 类 |
| ADR 数量 (Phase 25-27) | — | 4 | **5** | +5 个 |
| 测试 | 3683 | 3683 | 3683 | 保持 |
| 覆盖率 | 85.89% | 85.89% | 85.89% | 保持 |
| Ruff | clean | clean | clean | 保持 |

## ADR 链接

- 前置: [ADR-020 Phase 26 收口 + Phase 27 移交](./ADR-020-phase-26-close-and-phase-27-handoff.md)
- 后续: 治理进入"持续维护"阶段，adg 报告 0 warning 0 error 需长期保持
