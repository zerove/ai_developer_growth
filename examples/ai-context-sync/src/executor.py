import concurrent.futures
from typing import Any, Callable, Dict, List

from .logger import logger


class ParallelExecutor:
    """
    Executes a set of dependent sub-tasks in parallel using a thread pool.
    """

    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers

    def execute(
        self, tasks: List[Dict[str, Any]], task_fn: Callable[[Dict], Any]
    ) -> Dict[str, Any]:
        """
        Executes tasks based on their dependencies.
        tasks: List of task objects with 'id', 'depends_on', and other data.
        task_fn: The function to execute for each task (e.g., a call to LLM).
        """
        results = {}
        pending_tasks = {t["id"]: t for t in tasks}

        while pending_tasks:
            # Find tasks that have all dependencies met
            ready_tasks = [
                t
                for tid, t in pending_tasks.items()
                if all(dep in results for dep in t.get("depends_on", []))
            ]

            if not ready_tasks:
                # Deadlock or circular dependency
                logger.error(
                    "Circular dependency detected or unresolvable tasks in implementation plan."
                )
                break

            logger.info(
                f"🚀 Executing batch of {len(ready_tasks)} tasks in parallel..."
            )

            with concurrent.futures.ThreadPoolExecutor(
                max_workers=self.max_workers
            ) as executor:
                # Map task_fn to the ready tasks
                future_to_task = {
                    executor.submit(task_fn, t): t["id"] for t in ready_tasks
                }

                for future in concurrent.futures.as_completed(future_to_task):
                    tid = future_to_task[future]
                    try:
                        results[tid] = future.result()
                        logger.info(f"✅ Task {tid} completed.")
                    except Exception as e:
                        logger.error(f"❌ Task {tid} failed: {e}")
                        results[tid] = None

            # Remove completed tasks from pending
            for t in ready_tasks:
                pending_tasks.pop(t["id"], None)

        return results
