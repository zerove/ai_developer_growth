# ADR-040: Phase 33 子任务 33a-2 semantic_checker 私有方法覆盖

## 状态
接受（补记：2026-10-02 追补）

## 日期
2026-09-03

## 背景

本 ADR 是**追补记录**。Phase 33 子任务 33a-2（semantic_checker 私有方法补测）当时
已实际完成，但决策记录未落盘，导致 `ADR.md` 索引在 ADR-039 与 ADR-041 之间留下
编号缺口 —— ADR-040 长期"有编号、无文件、有内容、无记录"。

追补依据（2026-10-02 核对 `tests/` 实测）：

- `tests/test_semantic_checker_private.py` 存在，13 个用例，对应 33a-2 计划中的
  "私有 cache 方法"覆盖
- ADR-039（33a-1 纯函数）记录"semantic_checker.py 73% → 78%"，并预告
  "后续 33a-2/3/4 推进"
- ADR-041（33a-3 公开 API）明确写"在 33a-1 纯函数 (12 测试) 与 **33a-2 私有方法
  (13 测试)** 之后"，用例数与 `test_semantic_checker_private.py` 实际 13 个一致
- ADR-036（Phase 33 规划）列出 33a-2 "私有 cache 函数 (1h)" 为既定子任务

即：33a-2 的产出与外部引用均已存在，唯独决策记录缺失。属**记录缺口**而非工作缺口。

## 决策

**追补 ADR-040 记录 33a-2 的范围与结论，编号不复用、不重排后续 ADR。**

覆盖的私有方法（`semantic_checker.py`）：

| 方法 | 职责 |
|---|---|
| `_collect_source_files` | 目录扫描 + 语言过滤 + `max_files` 截断 |
| `_parse_single_file` | 单文件 AST 解析 |
| `_check_complexity` | 函数长度 / 圈复杂度超限判定 |
| `_check_missing_docstrings` | 缺失 docstring 判定 |
| `_calculate_metrics` | 复杂度指标汇总 |

配套测试分布（`tests/` 实测）：

| 文件 | 用例数 | 对应子任务 |
|---|---|---|
| `test_semantic_checker_pure.py` | 12 | 33a-1（ADR-039） |
| `test_semantic_checker_private.py` | 13 | **33a-2（本 ADR）** |
| `test_semantic_checker_public_api.py` | 31 | 33a-3（ADR-041） |
| `test_semantic_checker_deep.py` | 10 | 33a-1/2 边界路径 |

## 后果

- `ADR.md` 索引不再有 ADR-039 → ADR-041 的编号断层
- 后续读者可据 ADR-041 的交叉引用找到 33a-2 的真实记录
- ADR-006 保持历史空号不复用（既有约定，见 `ADR.md` 末尾注记）

## 相关

- ADR-036: Phase 33 启动规划（含 33a-1 ~ 33a-4 子任务分解）
- ADR-039: 33a-1 纯函数覆盖
- ADR-041: 33a-3 公开 API 集成补测（交叉引用 33a-2 的 13 测试）
- ADR-042: 33a-4 ASTParser LRU/snapshot 补测
