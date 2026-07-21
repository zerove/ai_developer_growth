.PHONY: help install lint format type-check test test-cov check security clean all

# Default target
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ──────────────────────────────────────────────────────
# Setup
# ──────────────────────────────────────────────────────

install: ## Install all dependencies
	pip install -r requirements.txt
	pip install -r requirements-dev.txt 2>/dev/null || true
	pip install ruff mypy pytest pytest-cov bandit pip-audit pre-commit

install-pre-commit: ## Install pre-commit hooks
	pre-commit install

# ──────────────────────────────────────────────────────
# Code Quality
# ──────────────────────────────────────────────────────

lint: ## Run ruff linter
	ruff check .
	ruff format --check .

format: ## Auto-format code with ruff
	ruff format .
	ruff check --fix .

type-check: ## Run mypy type checker
	mypy tools/scripts/ --ignore-missing-imports

# ──────────────────────────────────────────────────────
# Testing
# ──────────────────────────────────────────────────────

test: ## Run all tests
	python -m pytest tests/ -v --tb=short

test-cov: ## Run tests with coverage report
	python -m pytest tests/ -v --cov=tools/scripts --cov-report=term-missing --cov-report=xml --tb=short

test-fast: ## Run tests without coverage (faster)
	python -m pytest tests/ -v --tb=short -x

# ──────────────────────────────────────────────────────
# Quality Gates
# ──────────────────────────────────────────────────────

security: ## Run security scans (bandit + pip-audit)
	bandit -r tools/scripts/ -f json -o bandit-report.json || true
	pip-audit --desc

links: ## Check documentation links
	python tools/scripts/link_auditor.py . --check-all

validate-cases: ## Validate all case studies
	python tools/scripts/validate_case_study.py --all --strict

audit: ## Run governance audit
	python tools/scripts/audit_to_pr.py --check-all

# ──────────────────────────────────────────────────────
# Combined
# ──────────────────────────────────────────────────────

check: lint type-check test ## Run all checks (lint + type-check + test)

pre-commit: ## Run pre-commit on all files
	pre-commit run --all-files

# ──────────────────────────────────────────────────────
# Cleanup
# ──────────────────────────────────────────────────────

clean: ## Remove build artifacts and caches
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .mypy_cache .ruff_cache htmlcov coverage.xml .coverage bandit-report.json

# ──────────────────────────────────────────────────────
# All
# ──────────────────────────────────────────────────────

all: clean install check security ## Full pipeline: clean + install + check + security
