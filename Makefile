.PHONY: lint test check

lint:
	ruff check src/ tools/ tests/ examples/ai-context-sync/src/
	ruff format --check src/ tools/ tests/ examples/ai-context-sync/src/

test:
	cd examples/ai-context-sync && python -m pytest tests/ -v --timeout=30
	python -m pytest tests/ -v --timeout=30

check: lint test
