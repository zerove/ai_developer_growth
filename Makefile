.PHONY: lint test check

lint:
	ruff check tools/ tests/ examples/ai-context-sync/src/ examples/self-correction-loop/src/ examples/multi-agent-orch/src/ scripts/
	ruff format --check tools/ tests/ examples/ai-context-sync/src/ examples/self-correction-loop/src/ examples/multi-agent-orch/src/ scripts/

test:
	cd examples/ai-context-sync && PYTHONPATH=src python -m pytest tests/ -v
	python -m pytest tests/ -v
	cd examples/self-correction-loop && PYTHONPATH=src python -m pytest tests/ -v
	cd examples/multi-agent-orch && PYTHONPATH=src python -m pytest tests/ -v
	cd examples/ai-task-prioritizer && python -m pytest tests/ -v
	cd examples/capability-radar && python -m pytest tests/ -v

check: lint test