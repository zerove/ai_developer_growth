.PHONY: help lint format format-fix typecheck test test-cov check-quality security audit validate-docs check-index sync-refs validate-governance-docs check-ai-sdlc audit-hallucination link-audit validate-cases scan full-audit full-validate docs-build test-fast check release setup-git workflow-pr workflow-weekly workflow-release clean quick discover jcode list-tools new-skill release-version cov-diff cov-module cov-gate cov-snapshot context-status context-split stats stats-check

help:  ## 显示帮助信息
	@grep -hE '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

lint:  ## 运行 lint 检查
	python -m tools.scripts.hooks_runner lint

format:  ## 运行 ruff format 检查
	python -m tools.scripts.hooks_runner format

format-fix:  ## 自动修复格式
	python -m tools.scripts.hooks_runner format --fix

typecheck:  ## 运行 mypy 类型检查
	python -m tools.scripts.hooks_runner typecheck

test:  ## 运行 pytest 测试 (并行, 始终产出覆盖率报告)
	python -m tools.scripts.hooks_runner test

test-cov:  ## 同test —— 覆盖率已始终启用, 保留此名仅为向后兼容
	@echo "注意: 覆盖率已始终启用 (--cov=tools --cov=.jcode/scripts), test-cov 等价于 test"
	@$(MAKE) --no-print-directory test

check-quality:  ## 运行完整质量检查 (lint + format + typecheck + test + coverage)
	python -m tools.scripts.hooks_runner full

security:  ## 运行安全扫描
	python -m tools.scripts.hooks_runner security

audit:  ## 运行治理审计 (lint + format + typecheck + test)
	python .jcode/scripts/governance-auditor.py lint
	python .jcode/scripts/governance-auditor.py format
	python .jcode/scripts/governance-auditor.py typecheck
	python .jcode/scripts/governance-auditor.py test

validate-docs:  ## 验证治理文档格式
	python .jcode/scripts/governance-docs-validator.py validate

check-index:  ## 检查治理文档索引引用
	python .jcode/scripts/governance-docs-validator.py check-index

sync-refs:  ## 同步治理文档交叉引用
	python .jcode/scripts/governance-docs-validator.py sync-refs

validate-governance-docs:  ## 验证治理层文档完整性
	python .jcode/scripts/governance-auditor.py validate-governance-docs

check-ai-sdlc:  ## 检查 AI-SDLC 合规性
	python .jcode/scripts/governance-auditor.py check-ai-sdlc-compliance

audit-hallucination:  ## 审计幻觉风险
	python .jcode/scripts/governance-auditor.py audit-hallucination-risks

link-audit:  ## 检查文档断链
	python tools/scripts/link_auditor.py . --check-all

validate-cases:  ## 验证案例格式
	python tools/scripts/validate_case_study.py --all --strict

scan:  ## 扫描案例格式完整性
	python .jcode/scripts/knowledge-curator.py scan

full-audit:  ## 运行完整审计 (所有检查)
	python .jcode/scripts/governance-auditor.py full

full-validate:  ## 运行
	python .jcode/scripts/governance-docs-validator.py full

docs-serve:  ## 启动 mkdocs 本地服务器
	mkdocs serve

docs-build:  ## 构建文档
	mkdocs build --strict

test-fast: ## 运行快速测试（跳过 @pytest.mark.slow）
	python -m pytest tests/ -q -m "not slow" --tb=short

doctor:  ## 诊断本地门禁环境（工具链/插件/基线是否就绪）
	@python -m tools.scripts.hooks_runner doctor

ci-heartbeat:  ## 检测远端 CI 是否真的跑过 job（必须本地运行，见 ADR-057）
	@python -m tools.scripts.hooks_runner ci-heartbeat

ci-alert:  ## 同 ci-heartbeat，额外以去重 Issue 方式开/更新告警、恢复时自动关闭
	@python -m tools.scripts.hooks_runner ci-heartbeat --alert

self-check: doctor ci-heartbeat  ## 自检：本地环境 + 远端门禁存活
	@echo "✅ 自检完成（本地环境就绪 且 远端 CI 存活）"

check: lint format typecheck test validate-docs check-index semantic-graph architecture-guard  ## 运行所有检查 (包含 AI-Native 门禁)

semantic-graph:  ## 生成语义代码知识图谱
	python -m tools.scripts.semantic_code_graph

architecture-guard:  ## 运行架构漂移防御检查
	python -m tools.scripts.architecture_drift_guard

metrics-telemetry:  ## 收集研发效能与质量遥测数据
	python -m tools.scripts.metrics_telemetry

dashboard:  ## 启动 AI-Native 终端控制台驾驶舱
	python -m tools.scripts.ai_native_dashboard

mcp-server:  ## 启动 AI-Native 模型上下文协议 (MCP) 服务
	python -m tools.scripts.ai_native_mcp_server

multi-llm-route:  ## 运行多 LLM 智能模型路由决策
	python -m tools.scripts.multi_llm_router

# Release 自动化 (详见 Makefile.release)
-include Makefile.release

release: ## 完整发布流程 (版本递增 + CHANGELOG + Docker + 推送)
	@read -p "版本类型 (major/minor/patch) [patch]: " type; \
	type=$${type:-patch}; \
	make bump-$$type && \
	make docker-push VERSION=$$(python tools/scripts/release.py version) && \
	echo "✅ 发布完成: v$$(python tools/scripts/release.py version)"

setup-git: ## 配置 git 模板并安装 pre-push 门禁
	git config commit.template .gitmessage
	@python -m tools.scripts.hooks_runner install-hooks --pre-push
	@echo "✅ git 提交模板已配置 (.gitmessage)"
	@echo "✅ 提交格式: type(scope): 中文描述"
	@echo "✅ pre-push 门禁已安装 (来源 .jcode/hooks/pre-push)"

workflow-pr: ## 执行 PR 审查工作流 (registry.json)
	python .jcode/scripts/governance-auditor.py full
	python .jcode/scripts/knowledge-curator.py scan
	python .jcode/scripts/community-catalyst.py triage

workflow-weekly: ## 执行每周维护工作流 (registry.json)
	python .jcode/scripts/governance-auditor.py full
	python .jcode/scripts/knowledge-curator.py scan
	python .jcode/scripts/knowledge-curator.py audit
	python .jcode/scripts/workflow-optimizer.py report

workflow-release: ## 执行发布准备工作流 (registry.json)
	python .jcode/scripts/governance-auditor.py full
	python .jcode/scripts/knowledge-curator.py scan
	python .jcode/scripts/knowledge-curator.py audit
	python .jcode/scripts/workflow-optimizer.py report
	python .jcode/scripts/community-catalyst.py leaderboard

workflow-ai-native: ## 执行完整 JCode AI-Native 工作流主管道
	python -m tools.scripts.jcode_ai_native_workflow "JCode AI-Native Master Workflow Execution"

clean:  ## 清理临时文件
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .coverage coverage.xml bandit-report.json 2>/dev/null || true

# ─── 快速反馈循环 (P0-1) ─────────────────────────────────
quick:  ## 增量质量门禁 (lint + 仅改动相关测试, 5-60s)
	@echo "═══ [quick] lint 仅改动文件 ═══"
	@python -m tools.scripts.hooks_runner diff --base HEAD 2>/dev/null || python -m tools.scripts.hooks_runner lint
	@echo ""
	@echo "═══ [quick] test 仅改动相关模块 ═══"
	@python -m tools.scripts.hooks_runner test --incremental --base HEAD

quick-full:  ## 增量门禁无回退: 当 incremental 判定为空时仍跑 lint + typecheck
	@python -m tools.scripts.hooks_runner lint
	@python -m tools.scripts.hooks_runner typecheck
	@python -m tools.scripts.hooks_runner test --incremental --base HEAD

# ─── 统一入口 (P0-2) ─────────────────────────────────────
jcode:  ## 统一顶层入口(转发到 jcode_cli)
	@python -m tools.scripts.jcode_cli

list-tools:  ## 列出所有可用的工具脚本与 CLI 子命令
	@python -m tools.scripts.jcode_cli list-tools

discover:  ## 同 list-tools, 别名
	@$(MAKE) list-tools

new-skill:  ## 创建新 skill 骨架 (用法: make new-skill NAME=foo)
	@test -n "$(NAME)" || (echo "ERROR: NAME required, e.g. make new-skill NAME=foo"; exit 1)
	@mkdir -p .jcode/skills
	@printf "# %s\n\n## Description\n\nTODO: skill description.\n\n## Instructions\n\nTODO: skill instructions for the agent.\n" "$(NAME)" > .jcode/skills/$(NAME).md
	@echo "✓ Created .jcode/skills/$(NAME).md"

release-version:  ## 一键发版: lint→test→cov→升版→CHANGELOG→tag→push (用法: make release-version VERSION=2.13.0)
	@test -n "$(VERSION)" || (echo "ERROR: VERSION required, e.g. make release-version VERSION=2.13.0"; exit 1)
	@$(MAKE) test >/dev/null
	@echo "✓ tests passed"
	@$(MAKE) Makefile.release version-bump VERSION=$(VERSION) 2>/dev/null || (sed -i "s/^version = \".*\"/version = \"$(VERSION)\"/" pyproject.toml && uv lock >/dev/null 2>&1)
	@echo "✓ version bumped to $(VERSION)"
	@git add pyproject.toml uv.lock 2>/dev/null || true
	@git commit -m "chore(release): v$(VERSION)"
	@git tag -a v$(VERSION) -m "v$(VERSION)"
	@git push origin master --tags
	@git ls-remote origin refs/tags/v$(VERSION) | head -1
	@echo "✓ v$(VERSION) published"

# ─── 覆盖率 diff 与单模块门禁 (P1-1) ─────────────────────────
cov-snapshot:  ## 生成基线 coverage.json (用法: make cov-snapshot [OUTPUT=.jcode/cov-baseline.json])
	@python -m coverage json -o $(or $(OUTPUT),.jcode/cov-baseline.json) --include=tools/scripts/*
	@echo "✓ baseline written to $(or $(OUTPUT),.jcode/cov-baseline.json)"

cov-diff:  ## 对比覆盖率 (用法: make cov-diff OLD=a.json NEW=b.json [THRESHOLD=2.0])
	@python -m tools.scripts.cov_tool gate --coverage $(NEW) --baseline $(OLD) --threshold $(or $(THRESHOLD),2.0)

cov-module:  ## 单模块覆盖率详情 (用法: make cov-module MODULE=tools.scripts.foo)
	@python -m tools.scripts.cov_tool module --coverage $(or $(COVERAGE),coverage.json) --module $(MODULE)

cov-gate:  ## 与基线对比门禁 (用法: make cov-gate BASELINE=.jcode/cov-baseline.json [THRESHOLD=2.0])
	@python -m coverage json -o /tmp/cov-gate-current.json --include=tools/scripts/*
	@python -m tools.scripts.cov_tool gate --coverage /tmp/cov-gate-current.json --baseline $(BASELINE) --threshold $(or $(THRESHOLD),2.0)

context-status:  ## 输出项目实时快照 (版本/最新 tag/最近 5 commit/测试数)
	@python -m tools.scripts.context_status status

context-split:  ## 一次性拆分 CONTEXT.md: 滚动日志归档到 CHANGELOG (用法: make context-split [KEEP=5])
	@python -m tools.scripts.context_status split --keep $(or $(KEEP),5)

stats:  ## 输出项目统计 JSON (docs/cases/ADRs/tests/gate; 用法: make stats [SKIP_GATE=1])
	@python tools/scripts/update_stats.py --json $(if $(SKIP_GATE),--skip-quality-gate,)

stats-check:  ## 检查 README/统计漂移，非自动提交 (用法: make stats-check [SKIP_GATE=1])
	@python tools/scripts/update_stats.py --check $(if $(SKIP_GATE),--skip-quality-gate,)
