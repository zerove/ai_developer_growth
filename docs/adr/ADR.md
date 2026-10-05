---
title: 架构决策记录 (ADR) 索引
description: > 本文件汇总所有架构决策记录，按时间倒序排列。
category: 治理层
tags: ['REST']
difficulty: 基础
reading_time: 10 分钟
updated: 2026-09-17
---

# 架构决策记录 (ADR) 索引

> 本文件汇总所有架构决策记录，按时间倒序排列。

> ⚠️ **历史编号缺口**：ADR-001 ~ ADR-007 曾存在，但在 `649a947`（2026-07-28，标题为“全面优化 — 清理冗余”）中随文档整理一并删除，
> 且未留下替代记录。其中 ADR-003（四道质量门禁系统设计）等内容仍有实质价值。
> 下方表格只覆盖**当前磁盘上存在**的 ADR，因此从 ADR-010 开始。
> 这不是生成器的缺陷，而是历史归档缺失 —— 详见 CHANGELOG 与 ROADMAP 的待办。

---

## ADR 列表

<!-- BEGIN GENERATED ADR INDEX -->

| ID | 标题 | 状态 | 日期 |
|----|------|------|------|
| [[ADR-077-dry-run-must-not-mean-early-exit|ADR-077]] | "不写盘"与"提前退出"是两个语义，不得复用同一个布尔 | ✅ 已接受 | 2026-10-05 |
| [[ADR-076-parallel-worker-none-observable|ADR-076]] | worker 返回 None 与抛异常同等不可见，并行路径必须一并留痕 | ✅ 已接受 | 2026-10-04 |
| [[ADR-075-rules-disk-cache-cross-process-lock|ADR-075]] | 规则磁盘缓存必须跨进程加锁并原子写 | ✅ 已接受 | 2026-10-04 |
| [[ADR-074-worker-failure-must-be-observable|ADR-074]] | worker 失败不得静默丢结果，必须留下可追溯痕迹 | ✅ 已接受 | 2026-10-03 |
| [[ADR-073-test-isolation-cross-process-locks|ADR-073]] | 测试改写受控仓库文件必须跨进程互斥，且优先做到不碰工作区 | ✅ 已接受 | 2026-10-03 |
| [[ADR-072-auto-fix-verify-syntax-before-write|ADR-072]] | auto-fix 写盘前必须校验语法，且拒绝时不得声称已修复 | ✅ 已接受 | 2026-10-03 |
| [[ADR-071-directory-exit-code-on-rejection|ADR-071]] | 目录模式存在文件被拒时必须以非零退出 | ✅ 已接受 | 2026-10-03 |
| [[ADR-070-verify-syntax-before-writing|ADR-070]] | 写盘前必须校验修复结果的语法 | ✅ 已接受 | 2026-10-03 |
| [[ADR-069-auto-fix-must-not-break-syntax|ADR-069]] | 自动修复不得产出无法解析的代码 | ✅ 已接受 | 2026-10-03 |
| [[ADR-068-ast-fix-must-separate-found-from-applied|ADR-068]] | ast-fix 报告必须区分"发现"与"已应用" | ✅ 已接受 | 2026-10-03 |
| [[ADR-067-auto-safe-means-semantically-safe|ADR-067]] | auto_safe 只授予语义安全的改写 | ✅ 已接受 | 2026-10-03 |
| [[ADR-066-ast-fixer-must-persist-fixes|ADR-066]] | ASTFixer 报告的修复必须真正落盘 | ✅ 已接受 | 2026-10-03 |
| [[ADR-065-missing-path-must-fail|ADR-065]] | 路径不存在必须显式失败，禁止空集合假绿灯 | ✅ 已接受 | 2026-10-03 |
| [[ADR-064-semantic-degradation-must-be-visible|ADR-064]] | 语义检查降级必须可见，禁止 fail-open | ✅ 已接受 | 2026-10-03 |
| [[ADR-063-tree-sitter-per-language-import|ADR-063]] | tree-sitter 导入必须按语言粒度容错 | ✅ 已接受 | 2026-10-02 |
| [[ADR-062-fail-open-detector-validates-executability|ADR-062]] | fail-open 检测器必须校验"可执行性"，而非匹配错误关键词 | ✅ 已接受 | 2026-10-02 |
| [[ADR-061-context-header-outside-rolling-window|ADR-061]] | CONTEXT.md 固定头部必须独立于滚动窗口，且校验不得 fail-open | ✅ 已接受 | 2026-10-02 |
| [[ADR-060-adr-generator-non-interactive|ADR-060]] | adr_generator 必须能在非交互环境工作 | ✅ 已接受 | 2026-10-01 |
| [[ADR-059-security-patterns-dual-implementation|ADR-059]] | 安全模式两套实现并存是刻意设计，不做合并 | ✅ 已接受 | 2026-10-01 |
| [[ADR-058-context-sync-dual-implementation|ADR-058]] | context-sync 双实现并存是刻意设计，不做合并 | ✅ 已接受 | 2026-10-01 |
| [[ADR-057-ci-heartbeat-outside-ci|ADR-057]] | CI 静默失效根因确认 + 心跳检测器必须跑在 CI 之外 | ✅ 已接受 | 2026-09-29 |
| [[ADR-056-phase-36-complexity-gate|ADR-056]] | Phase 36 cc 门禁落地 + 18 个 ≥10cc 函数全量拆分 | ✅ 已接受 | 2026-09-17 |
| [[ADR-055-phase-35-file-split|ADR-055]] | Phase 35 大文件 facade 拆分（6 文件 <850 行） | ✅ 已接受 | 2026-09-15 |
| [[ADR-054-phase-34-dedup-common|ADR-054]] | Phase 34 跨文件重复函数抽取至 _common.py | ✅ 已接受 | 2026-09-15 |
| [[ADR-053-phase-33b13-check-directory-skipped|ADR-053]] | Phase 33b-13 check_directory 不再静默过滤 skipped 文件 | ✅ 已接受 | 2026-09-05 |
| [[ADR-052-phase-33b12-skipped-report-fix|ADR-052]] | Phase 33b-12 report_generator skipped 文件契约修复 | ✅ 已接受 | 2026-09-05 |
| [[ADR-051-phase-33b10-total-lines-fix|ADR-051]] | Phase 33b-10 ComplexityMetrics.total_lines 真实填充 | ✅ 已接受 | 2026-09-05 |
| [[ADR-050-phase-33b9-ast-parser-monster-e2e|ADR-050]] | Phase 33b-9 ast_parser monster.py 端到端契约验证 | ✅ 已接受 | 2026-09-05 |
| [[ADR-049-phase-33b8-ast-parser-multilang-iterative|ADR-049]] | Phase 33b-8 ast_parser 多语言 walk 与 complexity 迭代化扩展 | ✅ 已接受 | 2026-09-05 |
| [[ADR-048-phase-33b7-ast-parser-recursion-safety|ADR-048]] | Phase 33b-7 ast_parser 深度 AST 安全 (消除 RecursionError) | ✅ 已接受 | 2026-09-05 |
| [[ADR-047-phase-33b6-secret-scanner-scanned-files|ADR-047]] | Phase 33b-6 secret_scanner scanned_files 字段修复 | ✅ 已接受 | 2026-09-05 |
| [[ADR-046-phase-33b5-ast-parser-import-fix|ADR-046]] | Phase 33b-5 ast_parser import 解析 bug 修复 | ✅ 已接受 | 2026-09-05 |
| [[ADR-045-phase-33b3-4-semantic-rules-integration|ADR-045]] | Phase 33 子任务 33b-3/4 semantic_rules 集成测试 | ✅ 已接受 | 2026-09-05 |
| [[ADR-044-phase-33b2-semantic-rules-eval|ADR-044]] | Phase 33 子任务 33b-2 semantic_rules rule eval 补测 | ✅ 已接受 | 2026-09-05 |
| [[ADR-043-phase-33b1-semantic-rules-pure|ADR-043]] | Phase 33 子任务 33b-1 semantic_rules 纯函数覆盖 | ✅ 已接受 | 2026-09-05 |
| [[ADR-042-phase-33a4-ast-parser-lru-snapshot|ADR-042]] | Phase 33 子任务 33a-4 ASTParser LRU/snapshot 补测 | ✅ 已接受 | 2026-09-04 |
| [[ADR-041-phase-33a3-semantic-checker-public-api|ADR-041]] | Phase 33 子任务 33a-3 semantic_checker 公开 API 集成补测 | ✅ 已接受 | 2026-09-04 |
| [[ADR-040-phase-33a2-semantic-checker-private|ADR-040]] | Phase 33 子任务 33a-2 semantic_checker 私有方法覆盖 | ✅ 已接受 | 2026-09-03 |
| [[ADR-039-phase-33a1-semantic-checker-pure|ADR-039]] | Phase 33 子任务 33a-1 semantic_checker 纯函数覆盖 | ✅ 已接受 | 2026-09-03 |
| [[ADR-038-optimization-scan|ADR-038]] | 项目可优化内容分析 (全面扫描) | ✅ 已接受 | 2026-09-03 |
| [[ADR-037-setup-cfg-removal|ADR-037]] | setup.cfg 与 pyproject.toml mutmut 配置冲突修复 | ✅ 已接受 | 2026-09-03 |
| [[ADR-036-phase-33-planning|ADR-036]] | Phase 33 启动规划 - semantic_checker/semantic_rules 补测 | ✅ 已接受 | 2026-09-03 |
| [[ADR-035-public-api-actual-mapping|ADR-035]] | Phase 32 子任务 2e 实际公开 API 调研 | ✅ 已接受 | 2026-09-03 |
| [[ADR-034-yaml-merge-test-and-shared-ref|ADR-034]] | Phase 32 子任务 2d yaml/merge 覆盖 + 真实发现 | ✅ 已接受 | 2026-09-02 |
| [[ADR-033-rules-hash-mock-design|ADR-033]] | Phase 32 子任务 2c rules_hash mock 设计 | ✅ 已接受 | 2026-09-02 |
| [[ADR-032-disk-cache-mock-design|ADR-032]] | Phase 32 子任务 2b disk_cache mock 设计决策 | ✅ 已接受 | 2026-09-02 |
| [[ADR-031-test-permission-root-skip|ADR-031]] | test_rule_loader_file_hash 权限测试 root 跳过决策 | ✅ 已接受 | 2026-09-02 |
| [[ADR-030-phase-32-subtask-decomposition|ADR-030]] | Phase 32 启动 - rule_loader.py 补测子任务分解 | ✅ 已接受 | 2026-09-02 |
| [[ADR-029-phase-32-rule-loader-plan|ADR-029]] | Phase 32 rule_loader.py 覆盖率补测规划 | ✅ 已接受 | 2026-09-02 |
| [[ADR-028-regex-cache-test-and-bugfix|ADR-028]] | regex_cache iter_cached 修复 + 覆盖率补测 | ✅ 已接受 | 2026-09-02 |
| [[ADR-027-phase-30-rules-yml-first-intercept|ADR-027]] | Phase 30 双层防护主动拦截 .adg/rules.yml 污染事件 | ✅ 已接受 | 2026-09-02 |
| [[ADR-026-phase-30-hooks-json-integrity|ADR-026]] | Phase 30 .jcode/hooks.json fail-open 检测脚本 | ✅ 已接受 | 2026-09-01 |
| [[ADR-025-phase-30-rules-yml-on-merge|ADR-025]] | Phase 30 .adg/rules.yml 完整性 on_merge 双层防护 | ✅ 已接受 | 2026-09-01 |
| [[ADR-024-phase-29-mutmut-baseline|ADR-024]] | Phase 29 mutmut 突变测试基线 + 配置修正 | ✅ 已接受 | 2026-09-01 |
| [[ADR-023-phase-29-py-file-leak-misclassification|ADR-023]] | Phase 29 py-file-leak 误报识别 | ✅ 已接受 | 2026-09-01 |
| [[ADR-022-phase-28-empty-except-and-rules-recovery|ADR-022]] | Phase 28 空 except 治理原则 + .adg/rules.yml 恢复 | — | — |
| [[ADR-021-py-n-plus-one-profile-verdict|ADR-021]] | Phase 27 py-n-plus-one profile 验证结论 | — | — |
| [[ADR-020-phase-26-close-and-phase-27-handoff|ADR-020]] | Phase 26 收口与 Phase 27 移交 | — | — |
| [[ADR-019-phase-26-typo-cleanup|ADR-019]] | Phase 26 adg 误报再清理 | — | — |
| [[ADR-018-adg-rules-batch-downgrade|ADR-018]] | adg 规则批量降级总结 | — | — |
| [[ADR-017-py-log-print-downgrade|ADR-017]] | py-log-print 误报降级为 info | — | — |
| [[ADR-016-close-pending-adrs|ADR-016]] | 关闭 4 个长期未决 ADR (005/007/008/011) | 已通过 (2026-08-29) | — |
| [[ADR-015-pytest-xdist-race-condition|ADR-015]] | pytest-xdist race condition 接受现状 | ✅ 已接受 | — |
| [[ADR-014-checker-directory-complexity-refactor|ADR-014]] | 拆分 `check_directory` 复杂度炸弹 | ✅ 已接受 | — |
| [[ADR-013-pytest-xdist-coverage-known-issue|ADR-013]] | 覆盖率报告"假 0%" 现象 | ✏️ 已修订 | — |
| [[ADR-012-vector-rag-not-core|ADR-012]] | 向量 RAG 不作为 ai_developer_growth 检索核心 | ✅ 已接受 | — |
| [[ADR-011-phase18-ai-native-dialogue-community-cleanup|ADR-011]] | Phase 18 - 对话界面、社区案例清理、AI-Native 生态完善 | 已拆分关闭 (2026-08-29) | — |
| [[ADR-010-community-growth-infrastructure|ADR-010]] | P2 社区增长基础设施 | ✅ 已通过 | — |

<!-- END GENERATED ADR INDEX -->

---

## ADR 模板

新建 ADR 请复制以下模板，保存为 `docs/adr/ADR-{ID}-{title}.md`：

```markdown
# ADR-{ID}: {标题}

## 状态
{草稿 | 已通过 | 已废弃 | 已取代}

## 上下文
{描述问题背景和约束条件}

## 决策
{描述选择的方案和理由}

## 影响
{描述决策带来的正面和负面影响}

## 相关 ADR
- {如有依赖或取代关系，列出相关 ADR}
```

---

## 编号规则

- 格式: `ADR-{三位数字}-{简短标题}`
- 递增编号: ADR-001, ADR-002, ...
- 标题使用 kebab-case: `ADR-002-add-caching-layer`

---

## 创建流程

1. 识别需要记录的架构决策
2. 复制上方模板
3. 填写四部分内容
4. 提交 PR，等待评审
5. 合并后更新本索引

---

*本索引随新增 ADR 时更新。最后更新: 2026-09-17*
