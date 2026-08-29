# ADR-014: 拆分 `check_directory` 复杂度炸弹

## 状态
**Accepted** (2026-08-29)

## 背景
`tools/scripts/rules_engine/checker.py` 的 `check_directory` 函数 cyclomatic complexity
高达 **C=48**、**209 行**（超硬规则 50 行的 4 倍），是项目内最复杂函数。

### 风险
1. 单函数承担：规则合并 + 文件发现 + 缓存初始化 + 串/并行执行 + 架构分析
2. 任何修改需理解全部 5 个职责，未来改动高风险
3. 单元测试只能从外部覆盖，无法单测任一阶段

## 决策
按职责拆为 **4 个模块级 helper + 2 个执行 helper**：

| Helper | 行数 | C | 职责 |
|---|---|---|---|
| `_load_directory_rules` | 33 | 9 | 框架规则 + 域规则合并 |
| `_discover_target_files` | 38 | 3 | 文件发现 + 扩展名 + 排除 + 语言过滤 |
| `_init_cache_store` | 22 | 4 | 增量缓存初始化（失败回退） |
| `_run_architecture_analysis` | 33 | 7 | 跨文件依赖图 + 分层检查 |
| `_check_with_cache` | 49 | 9 | 单文件检查（命中缓存则跳过） |
| `_check_files_serial` | 23 | 4 | 串行执行（小集合） |
| `_check_files_parallel` | 43 | 7 | 并行执行（ProcessPoolExecutor） |
| `check_directory` (主) | 48 | 7 | 编排上述 6 个阶段 |

**总行数**: 209 → 48（主函数），所有 helper ≤ 50 行硬规则
**总复杂度**: 48 → 7（主函数），所有 helper ≤ 10

## 实施

### 拆分原则
1. **不改变外部签名**: `check_directory(...)` 参数完全保留
2. **不改变行为**: 9 个并行测试（`tests/test_adg_parallel.py`）全过
3. **保留回退语义**: 缓存失败/arch 模块 ImportError 等所有 try/except 路径保持
4. **类型注解完整**: 所有 helper 有完整 type hints

### 验证
- `python -c "import tools.scripts.rules_engine.checker"` → OK
- `pytest tests/test_adg_parallel.py -x` → 8/8 pass
- 全量测试待 v2.15.0 发版前跑

## 后果
- 单函数复杂度降至硬规则 1/7
- 未来修改任一阶段可独立单测
- 6 个新 helper 函数可独立 mock 测试
- 文件总行数 +70（多 helper docstring），但单点复杂度大幅下降

## 拒绝的方案
| 方案 | 理由 |
|---|---|
| 整体提取到新模块 | 改动面太大，需同步改 20+ 调用方 |
| 引入 ABC 基类 | 增加抽象层，YAGNI |
| 保留 nested function | 已尝试但 nonlocal 复杂，可读性差 |

## 参考
- v2.14.0 commit 81f3b58 (拆分前)
- v2.15.0 拆分后 commit (待发版)
- tests/test_adg_parallel.py (验证 8 用例)
