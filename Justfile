# JCode 开发命令统一入口
# 使用 just <command> 运行，just --list 查看所有命令

set shell := ["bash", "-cu"]

# 默认配置
export PYTHONPATH := "."
export UV_SYNC_OPTS := "--frozen"

# =============================================================================
# 核心质量检查
# =============================================================================

lint:
	ruff check .

format:
	ruff format --check .

format-fix:
	ruff format .

typecheck:
	mypy tools/scripts/ --ignore-missing-imports

test:
	python -m pytest tests/ -v -n auto

test-cov:
	python -m pytest tests/ -v -n auto --cov=tools/scripts --cov-report=term-missing --cov-report=xml --cov-report=html

test-fast:
	python -m pytest tests/ -q -m "not slow" --tb=short

check-quality: lint format typecheck test
	@echo "✅ 所有质量检查通过"

# =============================================================================
# 安全与合规
# =============================================================================

security:
	bandit -r tools/scripts/ -f json -o bandit-report.json || true
	pip-audit --desc

audit:
	just lint
	just format
	just typecheck
	just test

# =============================================================================
# 治理审计
# =============================================================================

validate-docs:
	python .jcode/scripts/governance-docs-validator.py validate

check-index:
	python .jcode/scripts/governance-docs-validator.py check-index

sync-refs:
	python .jcode/scripts/governance-docs-validator.py sync-refs

validate-governance-docs:
	python .jcode/scripts/governance-auditor.py validate-governance-docs

check-ai-sdlc:
	python .jcode/scripts/governance-auditor.py check-ai-sdlc-compliance

audit-hallucination:
	python .jcode/scripts/governance-auditor.py audit-hallucination-risks

# 完整治理审计
full-audit:
	python .jcode/scripts/governance-auditor.py full

full-validate:
	python .jcode/scripts/governance-docs-validator.py full

# =============================================================================
# 文档构建
# =============================================================================

docs-serve:
	mkdocs serve

docs-build:
	mkdocs build --strict

# =============================================================================
# AI-Native 工作流
# =============================================================================

semantic-graph:
	python tools/scripts/semantic_code_graph.py

architecture-guard:
	python tools/scripts/architecture_drift_guard.py

runtime-verify:
	python tools/scripts/runtime_verifier.py

self-healing-ci:
	python tools/scripts/self_healing_ci.py

slop-scan:
	python tools/scripts/ai_slop_scanner.py

metrics-telemetry:
	python tools/scripts/metrics_telemetry.py

dashboard:
	python tools/scripts/ai_native_dashboard.py

mcp-server:
	python tools/scripts/ai_native_mcp_server.py

self-evolve:
	python tools/scripts/self_evolving_engine.py

multi-llm-route:
	python tools/scripts/multi_llm_router.py

case-study-gen:
	python tools/scripts/case_study_pipeline.py

swarm-run:
	python tools/scripts/autonomous_swarm_engine.py

workflow-ai-native:
	python tools/scripts/jcode_ai_native_workflow.py "JCode AI-Native Master Workflow Execution"

# =============================================================================
# 工作流执行
# =============================================================================

workflow-pr:
	python .jcode/scripts/governance-auditor.py full
	python .jcode/scripts/knowledge-curator.py scan
	python .jcode/scripts/community-catalyst.py triage

workflow-weekly:
	python .jcode/scripts/governance-auditor.py full
	python .jcode/scripts/knowledge-curator.py scan
	python .jcode/scripts/knowledge-curator.py audit
	python .jcode/scripts/knowledge-curator.py update-moc
	python .jcode/scripts/workflow-optimizer.py report

workflow-release:
	python .jcode/scripts/governance-auditor.py full
	python .jcode/scripts/knowledge-curator.py scan
	python .jcode/scripts/knowledge-curator.py audit
	python .jcode/scripts/workflow-optimizer.py report
	python .jcode/scripts/community-catalyst.py leaderboard

# =============================================================================
# 知识管理
# =============================================================================

scan-cases:
	python .jcode/scripts/knowledge-curator.py scan

audit-cases:
	python .jcode/scripts/knowledge-curator.py audit

update-moc:
	python .jcode/scripts/knowledge-curator.py update-moc

link-audit:
	python tools/scripts/link_auditor.py . --check-all

validate-cases:
	python tools/scripts/validate_case_study.py --all --strict

# =============================================================================
# 社区催化剂
# =============================================================================

community-triage:
	python .jcode/scripts/community-catalyst.py triage

community-leaderboard:
	python .jcode/scripts/community-catalyst.py leaderboard

# =============================================================================
# 模式切换
# =============================================================================

mode-show:
	@echo "=== 当前模式 ===" && cat .jcode/mode_decision.conf

mode-perf:
	@printf "mode=perf\ngovernance_level=medium\naudit_enabled=false\n" > .jcode/mode_decision.conf
	@echo "✅ 切换到 perf 模式"

mode-quality:
	@printf "mode=quality\ngovernance_level=high\naudit_enabled=true\n" > .jcode/mode_decision.conf
	@echo "✅ 切换到 quality 模式"

mode-safe:
	@printf "mode=safe\ngovernance_level=high\naudit_enabled=true\n" > .jcode/mode_decision.conf
	@echo "✅ 切换到 safe 模式"

# =============================================================================
# 发布管理
# =============================================================================

release version="v0.0.0":
	@test -n "{{version}}" || (echo "用法: just release version=vX.Y.Z" && exit 1)
	@echo "📝 更新 CHANGELOG.md 版本为 {{version}} ..."
	@sed -i "s/## \[Unreleased\]/## [{{version}}] - $(date +%F)/" CHANGELOG.md 2>/dev/null || true
	git add CHANGELOG.md
	git commit -m "release: {{version}}"
	git tag -a {{version}} -m "{{version}}"
	git push origin master --tags --no-verify
	@echo "✅ {{version}} 发布完成"

# =============================================================================
# Git 配置
# =============================================================================

setup-git:
	git config commit.template .gitmessage
	@echo "✅ git 提交模板已配置 (.gitmessage)"
	@echo "✅ 提交格式: type(scope): 中文描述"

# =============================================================================
# 开发环境
# =============================================================================

setup:
	uv sync {{UV_SYNC_OPTS}}
	uv run pre-commit install
	@echo "✅ 开发环境就绪"

setup-dev:
	uv sync --all-extras {{UV_SYNC_OPTS}}
	uv run pre-commit install
	@echo "✅ 开发环境（含所有额外依赖）就绪"

# 依赖管理
deps-update:
	uv lock --upgrade
	uv sync {{UV_SYNC_OPTS}}

deps-audit:
	uv lock --check
	pip-audit

# 依赖锁文件同步
lock-sync:
	uv lock --upgrade
	uv sync {{UV_SYNC_OPTS}}

# =============================================================================
# 清理
# =============================================================================

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .coverage coverage.xml bandit-report.json 2>/dev/null || true
	@echo "✅ 清理完成"

clean-all: clean
	rm -rf .venv 2>/dev/null || true
	rm -rf dist build *.egg-info 2>/dev/null || true
	@echo "✅ 深度清理完成"

# =============================================================================
# 示例项目
# =============================================================================

# 为所有示例项目运行 CI
examples-ci:
	@for dir in examples/*/; do \
		if [ -f "$$dir/pyproject.toml" ]; then \
			echo "=== 运行 $$dir CI ==="; \
			(cd "$$dir" && uv run python -m pytest -v); \
		fi; \
	done

# =============================================================================
# Pre-commit
# =============================================================================

pre-commit-run:
	pre-commit run --all-files

pre-commit-update:
	pre-commit autoupdate

# =============================================================================
# 综合检查（CI 本地模拟）
# =============================================================================

ci-local: check-quality validate-docs check-index validate-governance-docs check-ai-sdlc audit-hallucination
	@echo "✅ 本地 CI 全部通过"

# =============================================================================
# 帮助别名
# =============================================================================

default: help

help:
	@just --list

# 交互式菜单
menu:
	@echo "JCode 开发命令菜单"
	@echo ""
	@echo "质量检查:"
	@echo "  just check-quality   - 完整质量检查"
	@echo "  just ci-local        - 本地模拟完整 CI"
	@echo ""
	@echo "治理审计:"
	@echo "  just full-audit      - 完整治理审计"
	@echo "  just full-validate   - 文档验证"
	@echo ""
	@echo "AI-Native:"
	@echo "  just workflow-ai-native - AI-Native 主管道"
	@echo "  just dashboard       - 终端控制台"
	@echo ""
	@echo "发布:"
	@echo "  just release version=vX.Y.Z"
	@echo ""
	@echo "环境:"
	@echo "  just setup           - 基础环境"
	@echo "  just setup-dev       - 全功能环境"
	@echo ""
	@echo "更多命令: just --list"