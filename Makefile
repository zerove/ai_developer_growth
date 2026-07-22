.PHONY: help lint format typecheck test test-cov security audit validate-docs check-index sync-refs full check clean

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

test:  ## 运行 pytest 测试
	python -m pytest tests/ -v

test-cov:  ## 运行测试
	python -m pytest tests/ -v --cov=tools/scripts --cov-report=term-missing --cov-report=html

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

check: lint format typecheck test validate-docs check-index  ## 运行所有检查

clean:  ## 清理临时文件
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .coverage coverage.xml bandit-report.json 2>/dev/null || true
