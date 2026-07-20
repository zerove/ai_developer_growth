# 变更日志

> 本文件记录项目所有重要变更。格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。
> 版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

---

## [0.3.0] - 2026-07-19

### 新增

- AI 时代开发者成长完整能力模型与验证体系
- 多 Agent 协作示例代码 (`examples/multi-agent-orch/`)
- 自我修正循环示例代码 (`examples/self-correction-loop/`)
- 测试覆盖率检查 (≥70%) 加入 GitHub Actions CI 流水线
- 审计报告文档 (`AUDIT_REPORT.md`)
- M3 社区启动计划草案

### 修复

- 修复构建系统问题，清理冗余依赖
- 清理测试文件 ruff linting 错误（未使用导入、未排序导入）
- 修复根目录测试路径引用

### 改进

- CLI 命令模块测试覆盖率从 64% 提升至 72%
- auditor.py 和 tools_evol.py 补充测试覆盖
- ruff --fix 自动修复 whitespace、import 排序、f-string 等（56 个文件）
- CONTEXT.md 更新以反映最新实施状态

---

## [0.2.0] - 2026-07-19

### 安全

- **SEC-01**: 修复任意文件写入漏洞 ([`orchestrator.py`](examples/ai-context-sync/src/orchestrator.py))，添加 `_validate_path()` 路径验证，拒绝绝对路径、`..` 遍历、项目目录外路径
- **SEC-02**: 修复未限制的文件覆盖漏洞 ([`monitoring.py`](examples/ai-context-sync/src/cli/commands/monitoring.py))，`apply_fix` 命令添加写入前路径安全检查
- **SEC-03**: 修复 API 密钥泄露漏洞 ([`gemini_provider.py`](examples/ai-context-sync/src/providers/gemini_provider.py))，API 密钥改为通过 Header 传递，不再嵌入 URL 查询参数

### 改进

- 项目综合审计完成，总评分 78/100
- 代码质量审计：ruff 发现 435 个问题，281 个可自动修复
- 测试通过 512+，ai-context-sync 覆盖率达 91.44%
- 文档完整性审计：识别 18 个断链
- CONTEXT.md、link_auditor 同步更新

### 新增

- 综合审计报告 (`AUDIT_REPORT.md`)
- ADR-001 至 ADR-004 架构决策记录体系

### 变更

- 项目路线图更新，明确 M1/M2 已完成、M3 社区计划

---

## [0.1.0] - 2026-07-18

### 新增

- **知识库核心**: 产品思维、独立开发闭环、AI-to-Market 清单、AI 驱动学习法、知识内化、Prompt 工程、全周期工作流、自动化 Bug 修复
- **工具矩阵**: 模型/IDE/Agent 选型指南
- **案例库**: 11 个实践案例，覆盖不同场景（AI 任务优先级工具、AI-Context-Sync 开发、遗留系统重构等）
- **治理框架**: GOVERNANCE.md 通用治理标准 + 13 种编程语言规范 + 11 种框架规范 + 12 个领域规范
- **Agent 定义**: link-checker、context-sync-auditor、adr-generator、audit-to-pr 四个 Agent
- **参考实现**: AI-Context-Sync 知识验证工具（含 CLI、MCP 服务器、LLM 提供者）
- **模板系统**: ADR 模板、CONTEXT 模板、Prompt 模板
- **MCP 集成**: opencode MCP 服务器配置与使用指南

### 决策

- **知识优先重构** ([ADR-002](docs/adr/ADR-002-knowledge-first-restructure.md)): `products/ai_context_sync/` 移至 `examples/ai-context-sync/`，降级为参考实现，明确知识为第一价值
- **四道质量门禁** ([ADR-003](docs/adr/ADR-003-quality-gate-system.md)): 设计 Gate 1-4 质量检查体系，CI/CD 自动执行 Gate 2-3
- **多 Agent 协作模型** ([ADR-004](docs/adr/ADR-004-agent-collaboration-model.md)): 定义串行、并行、主从、对等四种编排模式

### 改进

- 项目治理文档完善，大文件重构
- 集成测试补充
- .opencode/ 内部状态文件忽略配置
- README、案例库、MCP 配置文档更新

---

## [0.0.1] - 2026-07-18

### 新增

- 项目初始化：AI 时代开发者成长知识库骨架搭建
- 初始文档结构：docs/、case-studies/、examples/、tools/、templates/
- 项目治理框架：CLAUDE.md、AGENTS.md、GOVERNANCE.md、UBIQUITOUS_LANGUAGE.md
- 知识地图：docs/MOC.md、INDEX.md
- 基础 CI/CD 配置（GitHub Actions）

---

*本文件随项目变更持续更新。*
