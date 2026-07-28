.PHONY: help lint format format-fix typecheck test test-cov check-quality security audit validate-docs check-index sync-refs validate-governance-docs check-ai-sdlc audit-hallucination link-audit validate-cases scan full-audit full-validate mode-show mode-set-perf mode-set-quality mode-set-safe docs-build test-fast check release setup-git workflow-pr workflow-weekly workflow-release clean

help:  ## 显示帮助信息
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

lint:  ## 运行
	ruff check .

format:  ## 运行 ruff format 检查
	ruff format --check .

format-fix:  ## 自动修复格式
	ruff format .

typecheck:  ## 运行 mypy 类型检查
	mypy tools/scripts/ --ignore-missing-imports

test:  ## 运行 pytest 测试 (并行)
	python -m pytest tests/ -v -n auto

test-cov:  ## 运行测试并生成覆盖率报告
	python -m pytest tests/ -v -n auto --cov=tools/scripts --cov-report=term-missing --cov-report=xml --cov-report=html

check-quality:  ## 运行完整质量检查 (lint + format + typecheck + test + coverage)
	echo '=== Ruff Check ===' && ruff check . && \
	echo '=== Ruff Format ===' && ruff format --check . && \
	echo '=== Mypy ===' && mypy tools/scripts/ --ignore-missing-imports && \
	echo '=== Tests ===' && python -m pytest tests/ -v -n auto --cov=tools/scripts --cov-report=term-missing && \
	echo '=== All checks passed ==='

security:  ## 运行安全扫描
	bandit -r tools/scripts/ -f json -o bandit-report.json || true
	pip-audit --desc

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

mode-show:  ## 查看当前模式
	@echo "=== 当前模式 ===" && cat .jcode/mode_decision.conf

mode-set-perf:  ## 切换到性能模式 (跳过 heavy 检查)
	@printf "mode=perf\ngovernance_level=medium\naudit_enabled=false\n" > .jcode/mode_decision.conf
	@echo "✅ 切换到 perf 模式"

mode-set-quality:  ## 切换到质量模式 (默认)
	@printf "mode=quality\ngovernance_level=high\naudit_enabled=true\n" > .jcode/mode_decision.conf
	@echo "✅ 切换到 quality 模式"

mode-set-safe:  ## 切换到安全模式 (最严格)
	@printf "mode=safe\ngovernance_level=high\naudit_enabled=true\n" > .jcode/mode_decision.conf
	@echo "✅ 切换到 safe 模式"

docs-serve:  ## 启动 mkdocs 本地服务器
	mkdocs serve

docs-build:  ## 构建文档
	mkdocs build --strict

test-fast: ## 运行快速测试（跳过 @pytest.mark.slow）
	python -m pytest tests/ -q -m "not slow" --tb=short

check: lint format typecheck test validate-docs check-index  ## 运行所有检查

release:  ## 创建新版本（需要 VERSION=vX.Y.Z）
	@test -n "$(VERSION)" || (echo "用法: make release VERSION=vX.Y.Z 例如: make release VERSION=v2.3.0" && exit 1)
	@echo "📝 更新 CHANGELOG.md 版本为 $(VERSION) ..."
	@sed -i "s/## \[Unreleased\]/## [$(VERSION)] - $$(date +%F)/" CHANGELOG.md 2>/dev/null || true
	git add CHANGELOG.md
	git commit -m "release: $(VERSION)"
	git tag -a $(VERSION) -m "$(VERSION)"
	git push origin master --tags --no-verify
	@echo "✅ $(VERSION) 发布完成"

setup-git: ## 配置 git 模板和钩子
	git config commit.template .gitmessage
	@echo "✅ git 提交模板已配置 (.gitmessage)"
	@echo "✅ 提交格式: type(scope): 中文描述"

workflow-pr: ## 执行 PR 审查工作流 (registry.json)
	python .jcode/scripts/governance-auditor.py full
	python .jcode/scripts/knowledge-curator.py scan
	python .jcode/scripts/community-catalyst.py triage

workflow-weekly: ## 执行每周维护工作流 (registry.json)
	python .jcode/scripts/governance-auditor.py full
	python .jcode/scripts/knowledge-curator.py scan
	python .jcode/scripts/knowledge-curator.py audit
	python .jcode/scripts/knowledge-curator.py update-moc
	python .jcode/scripts/workflow-optimizer.py report

workflow-release: ## 执行发布准备工作流 (registry.json)
	python .jcode/scripts/governance-auditor.py full
	python .jcode/scripts/knowledge-curator.py scan
	python .jcode/scripts/knowledge-curator.py audit
	python .jcode/scripts/workflow-optimizer.py report
	python .jcode/scripts/community-catalyst.py leaderboard

clean:  ## 清理临时文件
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .coverage coverage.xml bandit-report.json 2>/dev/null || true
