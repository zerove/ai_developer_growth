"""Tests for src/executor.py - ParallelExecutor"""

import os
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.executor import ParallelExecutor


class TestParallelExecutor:
    def test_init_default(self):
        executor = ParallelExecutor()
        assert executor.max_workers == 4

    def test_init_custom_workers(self):
        executor = ParallelExecutor(max_workers=2)
        assert executor.max_workers == 2

    def test_execute_single_task(self):
        executor = ParallelExecutor(max_workers=2)
        tasks = [{"id": "t1", "depends_on": [], "data": "hello"}]
        results = executor.execute(tasks, lambda t: t["data"].upper())
        assert results["t1"] == "HELLO"

    def test_execute_multiple_independent_tasks(self):
        executor = ParallelExecutor(max_workers=4)
        tasks = [
            {"id": "t1", "depends_on": []},
            {"id": "t2", "depends_on": []},
            {"id": "t3", "depends_on": []},
        ]
        results = executor.execute(tasks, lambda t: t["id"])
        assert len(results) == 3
        assert results["t1"] == "t1"
        assert results["t2"] == "t2"
        assert results["t3"] == "t3"

    def test_execute_dependent_tasks(self):
        executor = ParallelExecutor(max_workers=2)
        order = []
        lock = threading.Lock()

        def task_fn(t):
            with lock:
                order.append(t["id"])
            time.sleep(0.05)
            return t["id"]

        tasks = [
            {"id": "t1", "depends_on": []},
            {"id": "t2", "depends_on": ["t1"]},
            {"id": "t3", "depends_on": ["t2"]},
        ]
        results = executor.execute(tasks, task_fn)
        assert len(results) == 3
        # t1 before t2, t2 before t3
        assert order.index("t1") < order.index("t2")
        assert order.index("t2") < order.index("t3")

    def test_execute_failing_task(self):
        executor = ParallelExecutor(max_workers=2)
        tasks = [{"id": "t1", "depends_on": []}]

        def failing_fn(t):
            raise ValueError("Intentional failure")

        results = executor.execute(tasks, failing_fn)
        assert results["t1"] is None

    def test_execute_partial_failure(self):
        executor = ParallelExecutor(max_workers=2)
        tasks = [
            {"id": "t1", "depends_on": []},
            {"id": "t2", "depends_on": ["t1"]},
        ]

        def selective_fn(t):
            if t["id"] == "t1":
                raise RuntimeError("t1 failed")
            return "ok"

        results = executor.execute(tasks, selective_fn)
        assert results["t1"] is None
        # t2 should still execute even if t1 failed
        # (it has its dependency met with None value)
        assert results.get("t2") == "ok"

    def test_execute_empty_tasks(self):
        executor = ParallelExecutor()
        results = executor.execute([], lambda t: None)
        assert results == {}
