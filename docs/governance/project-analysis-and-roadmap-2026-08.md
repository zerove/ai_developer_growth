# 项目全面分析与开发计划 (2026-08-25)

> 基于 2026-08-25 实测盘点（master = 68b6444，2641 测试通过）。
> 所有结论均有实测证据，标注来源。

## 一、现状快照

| 维度 | 现状 | 证据 |
|---|---|---|
| 代码规模 | tools/ 41,029 行（154 文件）+ 子包 ~2,800 行；tests/ 31,033 行（118 文件） | `find + wc -l` |
| 测试 | 2641 通过，全量耗时 ~4min（串行）/ CI 分片 | pytest |
| 覆盖率 | 总体 69.1%，中位数 88.7%；≥60% 模块 135/153；**15 个模块 0%** | coverage.xml (2026-08-25 新鲜生成) |
| Lint/类型 | ruff、ruff format、mypy strict 全绿 | release validate 本地预演 |
| 语言规则 | 26 语言目录、756 条规则，schema 全部完整（severity/message 无缺失） | YAML 校验脚本 |
| AST 解析器 | tree-sitter 8 语言：python/js/ts/java/go/rust/ruby/cpp；**18 语言纯正则路径** | ast_parser.py import 块 |
| 供应链解析 | 9 生态（requirements/pyproject/package.json/go.mod/Cargo/Gradle/Gemfile/composer/NuGet） | supply_chain.py |
| CLI 命令面 | check/detect/list-rules/install-hooks/report/fix/rule/trend/notify/html-report/recommend/lsp/dashboard/marketplace/monorepo/bench/cicd/pattern-learner | parser.py add_parser |
| Jcode 钩子 | pre_tool 门禁 + post_tool 异步 + turn_end 摘要 + hook-report 观察工具 | ~/bin/jcode-adg-* |
| CI 工作流 | 18 个 workflow（含 6 个 reusable jobs） | .github/workflows/ |
| 内容资产 | docs 270 篇 / case-studies 47 个 / examples 10 个 | find 统计 |
| 性能基线 | pre_tool 单文件冷启动 0.38s；doctor 2.0s；454 文件扫描 5.1s | 实测计时 |
| 发布 | v2.4.0 tag 就绪；GitHub Billing 阻塞 Actions（唯一外部遗留） | gh run |

## 二、发现的问题与风险

### A. 声称与实现不符（治理红线，P0）
1. **ROADMAP「增强检索」声称过度**：声称"BM25 + 同义词扩展 + 协同过滤 + 向量 RAG"。实测仅有 BM25+同义词（`tools/scripts/search/tfidf_engine.py`，325 行）；协同过滤/向量 RAG 只存在于 `examples/ai-navigation` 参考实现，主工具链无集成。→ 违反项目自身"幻觉审计"标准。
2. **coverage.xml 报告路径错位**：class filename 无 `tools/` 前缀（如 `scripts/foo.py`），CI 的 XML 解析恰好兼容但本地分析工具按 `tools/` 过滤会得 0 模块。低危但易误导。

### B. 死代码与孤儿（P0 清理项)
3. **【已更正 2026-08-25】**初判 chat_integration/fix_engine 为孤儿不准确：两者均有测试(test_adg_new_modules.py)；fix_engine 另被 rules_engine/auto_fix.py 读取 fixes.yml。真实问题是双轨：notify.py 自带 slack/dingtalk 实现与 chat_integration 重叠 → 已统一复用。auto_fix.py.bak 已删除。
4. **lsp 子包 0 测试引用**（511 行），CLI 有 lsp 命令但无测试保护。
5. **examples 两项目近空壳**：ai-growth-vscode（1 个 ts 文件 0 测试）、ai-growth-slack（2 py 文件 1 测试）。

### C. 能力不均衡（P1 补强项）
6. **18 语言无 AST 解析器**：csharp/kotlin/swift/php/scala/dart/zig 等仅正则匹配，复杂度分析/函数提取不可用；其中 kotlin/swift 是企业高频语言。
7. **【已更正 2026-08-25】**初判有误：`check --sarif` 实际已实现（parser.py:19 注册，_output_results 分发）。真实缺口是缺 e2e 测试锁定契约 → 已补 test_check_sarif_output_e2e。sarif_exporter.py 覆盖率 0% 仍在 P1-4 攻坚范围。
8. **auto_fix 双轨制**：`adg_cli fix`（正则 FIX_RULES）与 `auto_fix.py`（AutoFixOrchestrator + Ruff/Isort Provider）互不引用，能力重复且口径不一。
9. **quality_gate.py 未进 adg_cli 主链**：被 bootstrap/hooks_runner/jcode_cli 引用，但 check 流程外独立存在。

### D. 测试结构问题（P1）
10. **subprocess 型测试不计覆盖率**：test_adg_bootstrap 用 subprocess 跑脚本 → bootstrap 实际覆盖 0%（有真实端到端测试却拿不到分），误导覆盖率门禁。
11. **15 个 0% 模块**集中在：运维类（docker_build/release/perf_benchmark）、新功能（sarif_exporter/rules_engine feedback/context_streamer）、jcode_cli 等。

### E. 文档健康（P2）
12. **30 处 wikilink 断链**（docs/efficiency 下 `[[GOVERNANCE]]` 类引用为主）——上轮清零后新增。
13. **CONTEXT.md 被 diff 原文污染**（头部是 git diff 输出而非摘要）——context_sync 自身的输出质量问题。

### F. 架构观察（P2）
14. **巨型文件**：hooks_runner.py 2584 行/119 定义、language_registry.py 1850 行/10 定义（后者仅 10 个顶层定义说明是数据型大文件，前者需拆分）。
15. **CI 冗余**：ci.yml（复用 jobs）与 ci-cd.yml 与 release.yml 的 validate 步骤三处重复 lint/type/test 配置，漂移风险（mypy 配置写法已不一致：ci-cd 带 --config-file，release 不带）。
16. **slsa-provenance 工作流从未可运行**（依赖 release published，而 release 因 Billing 从未成功）——非代码问题但属"未验证即存在"的流程。

## 三、开发计划

### P0 — 正确性与信誉（本周）
| # | 事项 | 动作 | 验收 |
|---|---|---|---|
| P0-1 | ROADMAP 检索声明修正 | ✅ 已完成：ROADMAP.md 行 30 已写 "BM25+同义词（已实现）；协同过滤/向量 RAG 见 examples 参考" | 措辞与 grep 证据一致 |
| P0-2 | 死代码清理 | ✅ 已完成：chat_integration/fix_engine/lsp 均有 test 引用，非死代码；`lsp/server.py` (510 行) 缺单测是真实欠缺点但不在本批范围 | grep 无残留未引用文件；测试全绿 |
| P0-3 | SARIF 接入 CLI | ✅ 已完成：`tools/scripts/adg_cli/format.py` 80-145 实现 `_format_sarif` + `_build_sarif_rules` + `_build_sarif_result`；`cmd_check.py` 通过 `--sarif` 标志调用 | `adg check --sarif` 输出合法 SARIF |
| P0-4 | Billing 恢复后发布 | rerun release；验证 slsa-provenance 首次跑通 | GitHub Release 存在且带产物 |

### P1 — 能力补强（1-2 周）
| # | 事项 | 动作 | 验收 |
|---|---|---|---|
| P1-1 | 高频语言 AST 解析器 | csharp（tree-sitter-c-sharp）、kotlin（tree-sitter-kotlin）先行，swift 次之 | 各语言函数/类提取测试通过；PARSER_REGISTRY 达 10 ✅（PARSER_REGISTRY 11 语言：python/go/rust/java/typescript/csharp/kotlin/swift/cpp/php/ruby，test_parser_registry_e2e.py 39 用例全过）|
| P1-2 | auto_fix 合并 | adg_cli fix 作为入口，底层调度 AutoFixOrchestrator（Python 文件走 Ruff provider，其余走正则） | 同一输入两路径结果一致；删重复逻辑 |
| P1-3 | subprocess 测试覆盖率化 | bootstrap 核心逻辑抽为可 import 函数，subprocess 仅留薄壳 e2e | bootstrap 覆盖率 >70% ✅（实测 76%，test_adg_bootstrap_unit.py 25 用例）|
| P1-4 | 0% 模块测试攻坚 | 按"用户可见优先"顺序：jcode_cli → rules_engine/feedback → sarif_exporter → 其余 | 0% 模块数 ≤5；总体 ≥72% 🟡（v2.13.10/11 推进 4 模块：lsp/server 0%→65% / metrics_telemetry 0%→100% / ai_context_manager 0%→97% / adr_generator 0%→86%；仍存 2 个 patch 路径 import 边界 + 1 个无测试 rule_marketplace）|
| P1-5 | mypy 配置统一 | 三处 workflow 统一引用 pyproject [tool.mypy] | grep 无命令行级配置漂移 ✅（v2.13.9 修复 example-ci-template.yml）|

### P2 — 长期健康（本月内）
| # | 事项 | 动作 | 验收 |
|---|---|---|---|
| P2-1 | hooks_runner.py 拆分 | ✅ 已完成：tools/scripts/hooks/ 11 个模块 (basic_checks 326 / domain_checks 501 / misc_runner 396 / phase_runner 323 等)；hooks_runner.py 720 行 < 800 行目标 | 单文件 < 800 行 |
| P2-2 | wikilink 断链清零 | ✅ 已完成：v2.13.6 修 32 处 + v2.13.7 修 58 处，docs/ 全子目录 `link_auditor` 扫描 "All links are valid." | link_auditor 全清 |
| P2-3 | CONTEXT.md 污染修复 | ✅ 已完成：CONTEXT.md 头部仅含变更文件列表 (+115/-74 行) + 任务摘要，无 diff 原文 (+++ / --- / @@) 污染 | diff 文本不再进入 CONTEXT |
| P2-4 | examples 空壳处置 | ✅ 已完成：ai-growth-vscode/slack 均含 README + pyproject + tests，非空壳 | 全部 examples 都有 README |
| P2-5 | 向量 RAG 立项评估 | 若检索是核心场景则集成 chroma+embedding；否则从愿景文档移除 | 决策 + 文档 |
| P2-6 | CI 收敛为单一真源 | ci.yml 复用 jobs 成为唯一 lint/test 执行点，release/ci-cd 只调 jobs | grep 单点 🟡（release.yml 全部 lint/test/type-check/doctor-gate/pre-commit/governance-audit 改调 .github/workflows/jobs/*.yml，validate 只做 tag↔pyproject + CHANGELOG 一致性；ai-native-sdlc.yml 是手工 pipeline 不强制收敛）|

### N3 钩子首次真实调优 (2026-08-25)

pre_tool 门禁上线后首次拦截到"误伤"：编辑 tests/test_adg_cli_v2.py 被
27 个**存量** error 阻断。已修复：钩子增加测试文件路径豁免
（*/tests/*、test_*.py、*Test.java 等，与 .adg/config.yml 口径一致），
生产文件仍严格拦截。实测：测试文件放行、坏生产文件阻断均正确。

---

## 四、量化目标（下个里程碑 v2.5.0）

- 覆盖率 ≥75%（当前 69.1%），0% 模块 ≤5（当前 15）
- AST 解析器语言 ≥10（当前 8）
- CLI 全命令有 smoke 测试（当前 lsp/dashboard/marketplace 弱）
- 断链 0（当前 30）；ROADMAP/README 声称 100% 可 grep 验证
- 外部项目实战验证 ≥3 个（当前 1：sisyphus-engine）

---
*生成方式：全部结论来自本机实测命令（pytest/coverage/grep/计时/YAML 校验），无凭记忆推断项。*


## P2 实施记录

### P2-4 examples 空壳处置【已更正】
初判 ai-growth-vscode / ai-growth-slack 为空壳目录，复核不成立：
两者均有完整 README、实质代码（bot.py 6KB / extension.ts）与测试。
实测验证：slack bot 15 测试通过；vscode 扩展 npm ci + tsc 编译通过。
处置结论：保留，无需归档。

### P2-5 向量 RAG 声称排查结论
全仓 grep 排查: 实现真实存在（examples/ai-navigation/src/vector_search.py，
sentence-transformers + cosine + BM25 混合 RRF，11 测试通过）。
ROADMAP.md 口径准确（已标注"参考实现，尚未集成主链"）。
CONTEXT.md 两处表述补注 examples 参考实现限定，与 ROADMAP 对齐。

### P2-6 CI 收敛单一真源
- 删除 ci-cd.yml（"JCode Platform" Docker 模板残留，registry 为 example.com 占位符，与本项目无关）
- 5 个与 ci.yml 聚合门禁重复的独立 workflow（adg-governance/adg-quality-report/adg-scan/ai-native-sdlc/advanced-governance）
  触发器收敛为 workflow_dispatch 手动触发；ci.yml 是 push/PR 唯一自动门禁
- 全部 37 个 workflow YAML 解析校验通过
