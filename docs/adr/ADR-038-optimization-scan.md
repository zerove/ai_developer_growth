# ADR-038: 项目可优化内容分析 (全面扫描)

## 状态
接受 (分析报告, 修复待 Phase 34+)

## 日期
2026-09-03

## 背景

第 5 次"全面分析"中,扫描项目实现以找可优化内容。
这不是"找 bug" (B 已扫过),而是找**代码质量 + 可维护性**提升点。

## 扫描维度

### 维度 1: 大文件 (>1k 行, 拆分候选)
- `language_registry.py` (1898 行)
- `analyze_case_quality.py` (919 行)
- `supply_chain.py` (1190 行)
- `rules_engine/ast_parser.py` (1148 行)

### 维度 2: 高圈复杂度函数 (>=10 cc, 重构候选)
15 个函数圈复杂度 ≥ 8-10, 其中 7 个 ≥ 10:
- `dependency_graph.py::_run_tarjan_scc` (10 cc, 44 lines)
- `jcode_cli.py::_list_standalone_scripts` (10 cc)
- `update_ai_tool_matrix.py::update_matrix` (10 cc)
- `fix_heuristics.py::_try_message_heuristics` (10 cc)
- `adg_cli/check.py::check_file` (10 cc, 30 lines)
- `rules_engine/checker.py::check_file` (10 cc, 67 lines)
- `rules_engine/plugins.py::discover_plugins` (10 cc, 46 lines)

### 维度 3: 重复函数定义 (跨文件同名私有函数)
**真实发现: 72 组重复** (同名 `_xxx` 函数在 >1 文件定义), 示例:
- `_apply_fix` (2 处)
- `_check_pattern` (3 处)
- `_child_by_type` (9 处, parser 类)
- `_check_files_parallel` (2 处)
- `_build_parser` (2 处)
- ...

这意味着**重复工具函数未抽取到共享模块**, 每次新工具都重新实现。

### 维度 4: 死代码候选
- 含 TODO/FIXME 文件: **8 个**
  - `rules_engine/ai_rules_generator.py`
  - `rules_engine/ast_fixer.py`
  - `rules_engine/hallucination_detector.py`
  - `rules_engine/auto_fix.py`
  - `secret_scanner.py`
  - `dor_checker.py`
  - `rule_editor.py`
  - `fix_heuristics.py`

### 维度 5: adg 误报数
- **5680 info issues** (info 级别, 非阻塞)
- 已降级 17 类规则, 但剩余数千条需评估

### 维度 6: 重复字符串
- `_load_yaml` 函数定义 (跨多个文件)
- adg_cli 多个文件重复字符串 "Rules loaded"

## 决策

### 决策 1: 优先级排序 (按 ROI)

| 优化项 | 工作量 | ROI | 风险 |
|--------|--------|-----|------|
| **重复函数抽取** (`_apply_fix` / `_check_pattern` / `_load_yaml` 等) | 2-3 天 | 高 (减 72 处重复) | 中 (需协调导入) |
| **大文件拆分** (语言注册表) | 1 天 | 中 (易读性) | 低 |
| **高 cc 函数重构** (7 个 ≥10 cc) | 1-2 天 | 中 | 中 (需测试) |
| **TODO/FIXME 清理** (8 文件) | 2-4 小时 | 低 | 极低 |
| **adg 误报再降级** | 1-2 天 | 中 | 低 |

### 决策 2: 不在本次会话启动修复

理由:
- session 已 42 commit, 不再延伸
- 优化是大工程, 应作为独立 Phase 34 启动
- 应先写测试再重构 (TDD)

### 决策 3: 建议 Phase 34 工作分解

```
Phase 34 重复函数抽取 (估时 2-3 天)
- 34a: 抽 _check_pattern 到 _common.py (3 处 → 1 处)
- 34b: 抽 _load_yaml 系列 (多文件 → 1 个工具)
- 34c: 抽 _apply_fix + _check_files_parallel
- 34d: 验证: ruff + mypy + pytest 全过

Phase 35 大文件拆分 (估时 1 天)
- 35a: language_registry.py 拆 (1898 → 5 个模块)
- 35b: supply_chain.py 拆 (1190 → 3 个模块)
- 35c: ast_parser.py 拆 (1148 → 4 个模块)

Phase 36 高 cc 重构 (估时 1-2 天)
- 36a: extract 方法降低圈复杂度 (≤5)
- 36b: 早返回 (early return) 减少嵌套
- 36c: 字典/策略模式替换 if-else 链

Phase 37 TODO/FIXME 清理 (估时 2-4 小时)
- 8 个文件逐一处理
- 决定: 实现 / 移除 / 标 deprecated

Phase 38 adg 误报再降级 (估时 1-2 天)
- 5680 info 中, 找 100-300 个高频误报
- 加 severity_overrides
```

## 后果

### 正面
- 全面扫描给出**量化**优化空间
- 重复函数 (72 组) 是**最高 ROI** (减少 72 处维护点)
- 大文件拆分 (1k+ 行 4 个) 是**易读性**提升
- 高 cc 重构提升**可测试性**

### 负面
- 4 个 Phase (34-38) 估时 5-9 天
- 涉及跨文件 import 协调, 风险中等
- 重构期间可能引入 bug (需测试覆盖)

## 验证

- AST 扫描覆盖 tools/scripts 下所有 .py
- 实测: 72 组重复函数 + 15 个高 cc + 4 个大文件 + 8 个 TODO
- 数据驱动决策, 无主观猜测

## 后续

Phase 34 估时 2-3 天, 应作为下一个 Phase 启动 (与 Phase 33 串行/并行都可)。
- Phase 33: 测试补测 (semantic_*, ADR-036)
- Phase 34: 代码质量优化 (本 ADR)

建议顺序: 先 Phase 33 (补测发现更多问题) → 后 Phase 34 (基于完整测试套重构)。
