import os
import subprocess
import json
import concurrent.futures
from typing import Dict, Any, List
from .logger import logger
from .llm_client import LLMClient
from .analyzer import GitAnalyzer
from .synthesizer import ContextSynthesizer
from .guard import ArchitectureGuard
from .auditor import SpecAuditor
from .tester import TestRunner
from .slicer import ContextSlicer
from .config import AppConfig
from .executor import ParallelExecutor
from .exceptions import WorkflowError, LLMError

class WorkflowManager:
    """
    Orchestrates the end-to-end AI-Native development flow:
    Sense -> Design -> Parallel Implement -> Global Audit -> Sync
    """
    
    def __init__(self, llm_client: LLMClient, analyzer: GitAnalyzer, 
                 synthesizer: ContextSynthesizer, guard: ArchitectureGuard, 
                 auditor: SpecAuditor, evolution: Any, config_path: str):
        self.llm_client = llm_client
        self.analyzer = analyzer
        self.synthesizer = synthesizer
        self.guard = guard
        self.auditor = auditor
        self.evolution = evolution
        self.config = AppConfig.load(config_path)
        self.tester = TestRunner(timeout=self.config.settings.test_timeout)
        self.slicer = ContextSlicer()
        self.executor = ParallelExecutor(max_workers=self.config.settings.executor_max_workers)

    def _write_to_file(self, path: str, content: str) -> None:
        """Helper to write content to a file."""
        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info(f"💾 Wrote content to {path}")

    def _execute_subtask(self, task: Dict[str, Any]) -> str:
        """
        The worker function that implements a single sub-task with an 
        autonomous implement-test-fix loop.
        """
        tid = task['id']
        desc = task['description']
        files = task['target_files']
        verification = task.get('verification', {})
        test_code = verification.get('test_code')

        if not test_code:
            logger.warning(f"No verification test provided for {tid}. Skipping loop and doing single-shot implementation.")
            # Fallback to single-shot (similar to old logic but using the new flow)
            return self._single_shot_implement(tid, desc, files)

        max_retries = self.config.settings.max_retries
        attempt = 0
        last_error = ""

        while attempt < max_retries:
            attempt += 1
            logger.info(f"🛠️ Worker executing {tid} (Attempt {attempt}/{max_retries}): {desc}")
            
            # 1. Generate/Fix Prompt with Sliced Context
            sliced_context = self.slicer.slice(files)
            if attempt == 1:
                prompt = (
                    f"Current Sliced Context:\n{sliced_context}\n\n"
                    f"Task ID: {tid}\n"
                    f"Description: {desc}\n"
                    f"Target Files: {files}\n"
                    f"Verification Test:\n{test_code}\n\n"
                    "Please implement the code that passes this test. "
                    "Return the result as file blocks: [FILE: path]\nCode...\n[END]\n"
                )
            else:
                prompt = (
                    f"Current Sliced Context:\n{sliced_context}\n\n"
                    f"Task ID: {tid}\n"
                    f"Description: {desc}\n"
                    f"Target Files: {files}\n"
                    f"Verification Test:\n{test_code}\n"
                    f"Previous Attempt Error:\n{last_error}\n\n"
                    "The previous implementation failed the verification test. "
                    "Please fix the code to ensure it passes the test. "
                    "Return the result as file blocks: [FILE: path]\nCode...\n[END]\n"
                )

            try:
                code_output = self.llm_client.generate(prompt, system_prompt="You are a focused implementation expert who writes test-passing code.")
                if not code_output:
                    return f"Error: No output for {tid}"
                
                # 2. Apply implementation to disk
                import re
                file_blocks = re.findall(r"\[FILE: (.*?)\]\n(.*?)\n\[END\]", code_output, re.DOTALL)
                for path, content in file_blocks:
                    self._write_to_file(path, content)
                
                # 3. Verify
                result = self.tester.run_test(test_code, files)
                if result.success:
                    logger.info(f"✅ Task {tid} passed verification on attempt {attempt}!")
                    return f"Successfully implemented and verified {tid}"
                
                last_error = result.output
                logger.warning(f"⚠️ Task {tid} failed verification (Attempt {attempt}):\n{last_error}")

            except (LLMError, OSError) as e:
                logger.error(f"Error in sub-task {tid} iteration {attempt}: {e}")
                last_error = str(e)

        return f"Failed {tid} after {max_retries} attempts. Last error: {last_error}"

    def run_flow(self, task: str, approval_callback: Any, initial_context: str = "") -> str:
        logger.info(f"🚀 Starting AI-Native Parallel Workflow for task: {task}")
        
        current_context, sub_tasks = self._phase_design(task, initial_context, approval_callback)
        if sub_tasks is None:
            return current_context  # Error or rejection message
        
        impl_result = self._phase_implement(sub_tasks, task)
        if impl_result:
            return impl_result
        
        audit_result = self._phase_audit(sub_tasks, task)
        if audit_result:
            return audit_result
        
        self._phase_sync(sub_tasks, task, current_context)
        self._phase_evolution()
        
        logger.info("✅ Parallel Workflow completed successfully.")
        return f"Task '{task}' completed. {len(sub_tasks)} sub-tasks implemented in parallel and verified."

    def _phase_design(self, task: str, initial_context: str, approval_callback: Any) -> tuple[str, Any]:
        current_context = initial_context or self.slicer.slice([])
        
        logger.info("📐 Phase 2: Generating technical design and task decomposition...")
        design_prompt = self._build_design_prompt(task, current_context)
        design_doc = self.llm_client.generate(design_prompt) or ""
        logger.info(f"\n--- Proposed Technical Design & Plan ---\n{design_doc}\n------------------------------\n")
        
        logger.info("🛡️ Running Architecture Design Drift Check...")
        drift_report = self.guard.check_design_drift(design_doc, task)
        logger.info(f"\n--- Architecture Drift Report ---\n{drift_report}\n----------------------------------\n")
        
        if not approval_callback():
            logger.info("❌ Design rejected. Workflow terminated.")
            return "Design rejected by user.", None

        try:
            start = design_doc.find("[")
            end = design_doc.rfind("]") + 1
            if start == -1 or end == 0:
                raise ValueError("No structured task list found in design.")
            sub_tasks = json.loads(design_doc[start:end])
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse sub-tasks from design: {e}")
            return "Design failed decomposition. Please refine the design.", None
        
        return current_context, sub_tasks

    def _phase_implement(self, sub_tasks: list, task: str) -> str:
        logger.info(f"💻 Phase 3: Implementing {len(sub_tasks)} sub-tasks in parallel...")
        results = self.executor.execute(sub_tasks, self._execute_subtask)
        
        failures = [tid for tid, res in results.items() if res is None or "Failed" in res]
        if failures:
            logger.error(f"❌ Some sub-tasks failed: {failures}")
            return f"Parallel implementation failed for tasks: {failures}"
        return ""

    def _phase_audit(self, sub_tasks: list, task: str) -> str:
        logger.info("⚖️ Phase 4: Running Global Spec Audit...")
        all_target_files = []
        for t in sub_tasks:
            all_target_files.extend(t.get('target_files', []))
            
        combined_diff = ""
        for f in set(all_target_files):
            if os.path.exists(f):
                with open(f, "r", encoding="utf-8") as file:
                    combined_diff += f"+++ b/{f}\n{file.read()}\n"

        import re
        max_audit_retries = 3
        for audit_attempt in range(1, max_audit_retries + 1):
            violations = self.auditor.audit(combined_diff, task)
            if not violations:
                logger.info("✨ Global Audit passed! All parallel modules comply.")
                return ""
            
            logger.warning(f"⚠️ Global Audit found {len(violations)} violations. Attempt {audit_attempt}/{max_audit_retries} to fix...")
            fix_prompt = (
                f"The parallel implementation of task '{task}' has the following spec violations:\n"
                f"{violations}\n\n"
                f"Please provide the corrected code for the affected files. "
                f"Return the result as file blocks: [FILE: path]\nCode...\n[END]"
            )
            fix_code = self.llm_client.generate(fix_prompt, system_prompt="You are a global integrator and quality gate.")
            if not fix_code:
                continue
            file_blocks = re.findall(r"\[FILE: (.*?)\]\n(.*?)\n\[END\]", fix_code, re.DOTALL)
            for path, content in file_blocks:
                self._write_to_file(path, content)
        
        logger.error("❌ Failed to reach global compliance after maximum retries.")
        return "Global Audit failed. Manual intervention required."

    def _phase_sync(self, sub_tasks: list, task: str, current_context: str) -> None:
        logger.info("🔄 Phase 5: Synchronizing project assets...")
        all_target_files = []
        for t in sub_tasks:
            all_target_files.extend(t.get('target_files', []))
        combined_diff = ""
        for f in set(all_target_files):
            if os.path.exists(f):
                with open(f, "r", encoding="utf-8") as file:
                    combined_diff += f"+++ b/{f}\n{file.read()}\n"
        updated_context = self.synthesizer.synthesize_context_update(combined_diff, task, current_context)
        with open(self.config.settings.context_file, "w", encoding="utf-8") as f:
            f.write(updated_context)

    def _phase_evolution(self) -> None:
        logger.info("💡 Phase 6: Checking for specification evolution opportunities...")
        candidates = self.evolution.analyze_conflicts()
        if candidates:
            logger.info(f"✨ Found {len(candidates)} evolution opportunities. Run 'dx evolve --batch' to propose updates.")

    def _single_shot_implement(self, tid: str, desc: str, files: list[str]) -> str:
        """Fallback implementation when no verification test is available."""
        logger.info(f"🛠️ Worker executing {tid} (single-shot): {desc}")
        prompt = (
            f"Task ID: {tid}\n"
            f"Description: {desc}\n"
            f"Target Files: {files}\n\n"
            "Please implement the code for this specific sub-task. "
            "Return the result as a series of file blocks: [FILE: path]\nCode...\n[END]\n"
        )
        try:
            code_output = self.llm_client.generate(prompt, system_prompt="You are a focused implementation expert.")
            if not code_output:
                return f"Error: No output for {tid}"
            import re
            file_blocks = re.findall(r"\[FILE: (.*?)\]\n(.*?)\n\[END\]", code_output, re.DOTALL)
            for path, content in file_blocks:
                self._write_to_file(path, content)
            return f"Successfully implemented {tid} (single-shot)"
        except Exception as e:
            logger.error(f"Error in single-shot sub-task {tid}: {e}")
            return f"Failed {tid}: {str(e)}"
    def _build_design_prompt(self, task: str, context: str) -> str:
        return (
            f"Task: {task}\n"
            f"Current Project Context:\n{context}\n\n"
            "Please provide a detailed technical design for this task. "
            "The design must include:\n"
            "1. Goal: High-level objective.\n"
            "2. Architecture Changes: What changes are needed in the system?\n"
            "3. API Changes: Specific interface updates.\n"
            "4. Implementation Plan: A detailed step-by-step plan.\n\n"
            "IMPORTANT: At the end of your response, you MUST provide a JSON list of independent sub-tasks "
            "for parallel implementation. Each task object should have:\n"
            "- 'id': unique task ID (e.g., 'TASK-1')\n"
            "- 'description': precise description of what to implement\n"
            "- 'target_files': list of files to be modified/created\n"
            "- 'verification': An object containing:\n"
            "    - 'test_code': a complete, runnable Python test script (using pytest or unittest) that verifies this specific sub-task.\n"
            "    - 'expected': a brief description of the expected behavior.\n"
            "- 'depends_on': list of task IDs that must be completed first (empty list if none)\n\n"
            "Example format:\n"
            "```json\n"
            "[\n"
            "  {\n"
            "    \"id\": \"TASK-1\",\n"
            "    \"description\": \"Implement the user greeting function\",\n"
            "    \"target_files\": [\"utils/greet.py\"],\n"
            "    \"verification\": {\n"
            "      \"test_code\": \"import pytest\\nfrom utils.greet import greet\\n\\ndef test_greet():\\n    assert greet('Alice') == 'Hello, Alice!'\",\n"
            "      \"expected\": \" greet('Alice') should return 'Hello, Alice!'\"\n"
            "    },\n"
            "    \"depends_on\": []\n"
            "  }\n"
            "]\n"
            "```"
        )

    def _build_test_prompt(self, task: str, design: str) -> str:
        return f"Task: {task}\nDesign:\n{design}\n\nPlease write a comprehensive set of unit tests (using pytest for Python) to verify this feature. Output only the code. Ensure you import the necessary modules from implementation.py."

    def _build_code_prompt(self, task: str, design: str, tests: str) -> str:
        return f"Task: {task}\nDesign:\n{design}\nTests:\n{tests}\n\nPlease implement the code that satisfies the design and passes the tests. Output only the code. Save it as implementation.py."
