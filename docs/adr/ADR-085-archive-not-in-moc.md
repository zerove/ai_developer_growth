# ADR-085: 归档层不纳入 MOC 导航

## 状态

接受

## 日期

2026-11-21

## 影响组件

- `tools/scripts/link_auditor.py`
- `tests/test_doc_index_reachability.py`

## 背景

2026-11-17 的十二个本地提交把 `scripts/optimization/` 整体迁入
`docs/archive/optimization/`。`link_auditor.py` 的
`find_moc_unreferenced_indexes()` 与
`tests/test_doc_index_reachability.py::test_every_index_is_referenced_by_moc`
对 `docs/archive/README.md` 判为"层索引孤儿"——MOC 导航未引用——
推送被门禁阻塞。

## 决策

`archive` 层不纳入 MOC 导航：

- `link_auditor.py` 在 `find_moc_unreferenced_indexes()` 里跳过
  `archive`（归档层收录已停维的历史资产，不是知识层）；
- `tests/test_doc_index_reachability.py` 同口径跳过 `archive`。

归档内容仍可单独阅读（`docs/archive/README.md` 作为目录解释），
只是没有 MOC 导航——属于刻意设计。

## 后果

- ✅ 推送不再被"archive 层孤儿"阻塞；
- ⚠️ `docs/archive/` 下的文档无自动化"入导航"保障——以后要恢复导航可重开此策略。
