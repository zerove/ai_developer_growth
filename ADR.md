# 架构决策记录 (ADR)

## 格式
- 标题: ADR-XXX: 简短描述
- 状态: 接受/废弃/替代
- 背景: 决策背景
- 决策: 具体决策
- 后果: 正面/负面影响

---

## 索引

| 编号 | 标题 | 状态 | 文件 |
|---|---|---|---|
| ADR-001 | Enhanced Git Analyzer | 接受 | [docs/adr/001-enhanced-git-analyzer.md](docs/adr/001-enhanced-git-analyzer.md) |
| ADR-001 | Language Rules Engine Architecture | 接受 | [docs/adr/001-language-rules-engine-architecture.md](docs/adr/001-language-rules-engine-architecture.md) |
| ADR-002 | Knowledge-First Restructure | 接受 | [docs/adr/002-knowledge-first-restructure.md](docs/adr/002-knowledge-first-restructure.md) |
| ADR-002 | Refactor Validate Language Rules | 接受 | [docs/adr/002-refactor-validate-language-rules.md](docs/adr/002-refactor-validate-language-rules.md) |
| ADR-003 | Quality Gate System | 接受 | [docs/adr/003-quality-gate-system.md](docs/adr/003-quality-gate-system.md) |
| ADR-003 | sys.path Shadowing | 废弃 | [docs/adr/003-sys-path-shadowing.md](docs/adr/003-sys-path-shadowing.md) |
| ADR-004 | Agent Collaboration Model | 接受 | [docs/adr/004-agent-collaboration-model.md](docs/adr/004-agent-collaboration-model.md) |
| ADR-004 | Config TOML Resilience | 接受 | [docs/adr/004-config-toml-resilience.md](docs/adr/004-config-toml-resilience.md) |
| ADR-005 | AI Navigation System | 接受 | [docs/adr/005-ai-navigation-system.md](docs/adr/005-ai-navigation-system.md) |
| ADR-007 | M4 AI Navigation Design | 接受 | [docs/adr/007-m4-ai-navigation-design.md](docs/adr/007-m4-ai-navigation-design.md) |
| ADR-008 | Production-Grade Workflow | 接受 | [docs/adr/008-production-grade-workflow.md](docs/adr/008-production-grade-workflow.md) |
| ADR-009 | CI/CD Optimization & Security | 接受 | [docs/adr/009-ci-cd-optimization-security.md](docs/adr/009-ci-cd-optimization-security.md) |
| ADR-010 | Community Growth Infrastructure | 接受 | [docs/adr/ADR-010-community-growth-infrastructure.md](docs/adr/ADR-010-community-growth-infrastructure.md) |
| ADR-011 | Phase 18 AI-Native Dialogue & Community Cleanup | 接受 | [docs/adr/ADR-011-phase18-ai-native-dialogue-community-cleanup.md](docs/adr/ADR-011-phase18-ai-native-dialogue-community-cleanup.md) |
| ADR-012 | 向量 RAG 不作为 ai_developer_growth 检索核心 | 接受 | [docs/adr/ADR-012-vector-rag-not-core.md](docs/adr/ADR-012-vector-rag-not-core.md) |
| ADR-013 | 覆盖率报告"假 0%" 现象 (修订) | 修订 | [docs/adr/ADR-013-pytest-xdist-coverage-known-issue.md](docs/adr/ADR-013-pytest-xdist-coverage-known-issue.md) |
| ADR-014 | 拆分 `check_directory` 复杂度炸弹 | 接受 | [docs/adr/ADR-014-checker-directory-complexity-refactor.md](docs/adr/ADR-014-checker-directory-complexity-refactor.md) |
| ADR-015 | pytest-xdist race condition 接受现状 | 接受 | [docs/adr/ADR-015-pytest-xdist-race-condition.md](docs/adr/ADR-015-pytest-xdist-race-condition.md) |
| ADR-016 | 关闭 4 个长期未决 ADR (005/007/008/011) | 接受 | [docs/adr/ADR-016-close-pending-adrs.md](docs/adr/ADR-016-close-pending-adrs.md) |
| ADR-017 | py-log-print 误报降级为 info | 接受 | [docs/adr/ADR-017-py-log-print-downgrade.md](docs/adr/ADR-017-py-log-print-downgrade.md) |
| ADR-018 | adg 规则批量降级总结 | 接受 | [docs/adr/ADR-018-adg-rules-batch-downgrade.md](docs/adr/ADR-018-adg-rules-batch-downgrade.md) |
| ADR-019 | Phase 26 adg 误报再清理 + 剩余 39 真问题移交 | 接受 | [docs/adr/ADR-019-phase-26-typo-cleanup.md](docs/adr/ADR-019-phase-26-typo-cleanup.md) |
| ADR-020 | Phase 26 收口与 Phase 27 移交 | 接受 | [docs/adr/ADR-020-phase-26-close-and-phase-27-handoff.md](docs/adr/ADR-020-phase-26-close-and-phase-27-handoff.md) |
| ADR-021 | Phase 27 py-n-plus-one profile 验证结论 | 接受 | [docs/adr/ADR-021-py-n-plus-one-profile-verdict.md](docs/adr/ADR-021-py-n-plus-one-profile-verdict.md) |
| ADR-022 | Phase 28 空 except 治理原则 + .adg/rules.yml 恢复 | 接受 | [docs/adr/ADR-022-phase-28-empty-except-and-rules-recovery.md](docs/adr/ADR-022-phase-28-empty-except-and-rules-recovery.md) |
| ADR-023 | Phase 29 py-file-leak 误报识别 + 修 1 真问题 | 接受 | [docs/adr/ADR-023-phase-29-py-file-leak-misclassification.md](docs/adr/ADR-023-phase-29-py-file-leak-misclassification.md) |
| ADR-024 | Phase 29 mutmut 配置修正 + 单文件 demo 基线 | 接受 | [docs/adr/ADR-024-phase-29-mutmut-baseline.md](docs/adr/ADR-024-phase-29-mutmut-baseline.md) |
| ADR-025 | Phase 30 .adg/rules.yml 完整性 on_merge 双层防护 | 接受 | [docs/adr/ADR-025-phase-30-rules-yml-on-merge.md](docs/adr/ADR-025-phase-30-rules-yml-on-merge.md) |
| ADR-026 | Phase 30 .jcode/hooks.json fail-open 检测脚本 | 接受 | [docs/adr/ADR-026-phase-30-hooks-json-integrity.md](docs/adr/ADR-026-phase-30-hooks-json-integrity.md) |
| ADR-027 | Phase 30 双层防护主动拦截 .adg/rules.yml 污染 | 接受 | [docs/adr/ADR-027-phase-30-rules-yml-first-intercept.md](docs/adr/ADR-027-phase-30-rules-yml-first-intercept.md) |
| ADR-028 | regex_cache iter_cached 修复 + 覆盖率补测 | 接受 | [docs/adr/ADR-028-regex-cache-test-and-bugfix.md](docs/adr/ADR-028-regex-cache-test-and-bugfix.md) |
| ADR-029 | Phase 32 rule_loader.py 覆盖率补测规划 | 接受 | [docs/adr/ADR-029-phase-32-rule-loader-plan.md](docs/adr/ADR-029-phase-32-rule-loader-plan.md) |
| ADR-030 | Phase 32 启动 - rule_loader 子任务分解 | 接受 | [docs/adr/ADR-030-phase-32-subtask-decomposition.md](docs/adr/ADR-030-phase-32-subtask-decomposition.md) |
| ADR-031 | test_rule_loader_file_hash 权限测试 root 跳过 | 接受 | [docs/adr/ADR-031-test-permission-root-skip.md](docs/adr/ADR-031-test-permission-root-skip.md) |
| ADR-032 | Phase 32 子任务 2b disk_cache mock 设计 | 接受 | [docs/adr/ADR-032-disk-cache-mock-design.md](docs/adr/ADR-032-disk-cache-mock-design.md) |
| ADR-033 | Phase 32 子任务 2c rules_hash mock 设计 | 接受 | [docs/adr/ADR-033-rules-hash-mock-design.md](docs/adr/ADR-033-rules-hash-mock-design.md) |
| ADR-034 | Phase 32 子任务 2d yaml/merge 覆盖 + 共享引用发现 | 接受 | [docs/adr/ADR-034-yaml-merge-test-and-shared-ref.md](docs/adr/ADR-034-yaml-merge-test-and-shared-ref.md) |
| ADR-035 | Phase 32 子任务 2e 实际公开 API 调研 | 接受 | [docs/adr/ADR-035-public-api-actual-mapping.md](docs/adr/ADR-035-public-api-actual-mapping.md) |
| ADR-036 | Phase 33 启动规划 - semantic_checker/semantic_rules | 接受 | [docs/adr/ADR-036-phase-33-planning.md](docs/adr/ADR-036-phase-33-planning.md) |
| ADR-037 | setup.cfg 与 pyproject.toml mutmut 配置冲突修复 | 接受 | [docs/adr/ADR-037-setup-cfg-removal.md](docs/adr/ADR-037-setup-cfg-removal.md) |
| ADR-038 | 项目可优化内容分析 (全面扫描) | 接受 | [docs/adr/ADR-038-optimization-scan.md](docs/adr/ADR-038-optimization-scan.md) |
| ADR-039 | Phase 33 子任务 33a-1 semantic_checker 纯函数覆盖 | 接受 | [docs/adr/ADR-039-phase-33a1-semantic-checker-pure.md](docs/adr/ADR-039-phase-33a1-semantic-checker-pure.md) |
| ADR-041 | Phase 33 子任务 33a-3 semantic_checker 公开 API 集成补测 | 接受 | [docs/adr/ADR-041-phase-33a3-semantic-checker-public-api.md](docs/adr/ADR-041-phase-33a3-semantic-checker-public-api.md) |
| ADR-042 | Phase 33 子任务 33a-4 ASTParser LRU/snapshot 补测 | 接受 | [docs/adr/ADR-042-phase-33a4-ast-parser-lru-snapshot.md](docs/adr/ADR-042-phase-33a4-ast-parser-lru-snapshot.md) |
| ADR-043 | Phase 33 子任务 33b-1 semantic_rules 纯函数覆盖 | 接受 | [docs/adr/ADR-043-phase-33b1-semantic-rules-pure.md](docs/adr/ADR-043-phase-33b1-semantic-rules-pure.md) |
| ADR-044 | Phase 33 子任务 33b-2 semantic_rules rule eval 补测 | 接受 | [docs/adr/ADR-044-phase-33b2-semantic-rules-eval.md](docs/adr/ADR-044-phase-33b2-semantic-rules-eval.md) |
| ADR-045 | Phase 33 子任务 33b-3/4 semantic_rules 集成测试 | 接受 | [docs/adr/ADR-045-phase-33b3-4-semantic-rules-integration.md](docs/adr/ADR-045-phase-33b3-4-semantic-rules-integration.md) |
| ADR-046 | Phase 33b-5 ast_parser import 解析 bug 修复 | 接受 | [docs/adr/ADR-046-phase-33b5-ast-parser-import-fix.md](docs/adr/ADR-046-phase-33b5-ast-parser-import-fix.md) |
| ADR-047 | Phase 33b-6 secret_scanner scanned_files 字段修复 | 接受 | [docs/adr/ADR-047-phase-33b6-secret-scanner-scanned-files.md](docs/adr/ADR-047-phase-33b6-secret-scanner-scanned-files.md) |

---

注：ADR 编号 006 为历史空号（已删除但未复用）。
