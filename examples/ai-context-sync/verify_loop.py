import os

from src.analyzer import GitAnalyzer
from src.auditor import SpecAuditor
from src.guard import ArchitectureGuard

# Use absolute imports via the package structure
from src.orchestrator import WorkflowManager
from src.profiles import LANGUAGE_PROFILES
from src.synthesizer import ContextSynthesizer


class MockLLMClient:
    """
    A mock LLM client that simulates a failing-then-passing sequence
    to test the autonomous verification loop.
    """
    def __init__(self):
        self.call_count = 0

    def generate(self, prompt, system_prompt=""):
        self.call_count += 1

        # 1. Handle Design Phase (Phase 2)
        if "provide a detailed technical design" in prompt:
            return (
                "Design: Implement calculate_sum in calc.py.\n\n"
                "```json\n"
                "[\n"
                "  {\n"
                "    \"id\": \"TASK-1\",\n"
                "    \"description\": \"Implement the calculate_sum function\",\n"
                "    \"target_files\": [\"calc.py\"],\n"
                "    \"verification\": {\n"
                "      \"test_code\": \"import calc\\n\\ndef test_sum():\\n    assert calc.calculate_sum(2, 3) == 5\",\n"
                "      \"expected\": \"calculate_sum(2, 3) should be 5\"\n"
                "    },\n"
                "    \"depends_on\": []\n"
                "  }\n"
                "]\n"
                "```"
            )

        # 2. Handle Implementation Phase (Phase 3)
        if "Task ID: TASK-1" in prompt:
            # Simulate a bug on the first attempt
            if "Previous Attempt Error" not in prompt:
                return "[FILE: calc.py]\ndef calculate_sum(a, b):\n    return a - b\n[END]"
            # Fix it on the second attempt
            else:
                return "[FILE: calc.py]\ndef calculate_sum(a, b):\n    return a + b\n[END]"

        # 3. Handle Audit Phase (Phase 4) - Return empty violations
        if "The parallel implementation of task" in prompt or "find ALL possible violations" in prompt:
            return "[]"

        return "Mock response"

def mock_approval():
    print("✅ Mock Approval: Design accepted.")
    return True

def main():
    # Setup with MockLLM
    llm = MockLLMClient()
    analyzer = GitAnalyzer()

    profile = LANGUAGE_PROFILES["python"]
    synthesizer = ContextSynthesizer(llm, profile)
    guard = ArchitectureGuard(llm, "docs/adr/")
    auditor = SpecAuditor(llm, "docs/specs/")

    config_path = ".ai-sync.json"
    if not os.path.exists(config_path):
        with open(config_path, "w") as f:
            f.write('{"settings": {"context_file": "CONTEXT.md"}}')

    wm = WorkflowManager(llm, analyzer, synthesizer, guard, auditor, config_path)

    task = "Implement a function 'calculate_sum' in 'calc.py' that takes two numbers and returns their sum."

    print(f"🚀 Testing Autonomous Loop with MockLLM: {task}")
    result = wm.run_flow(task, mock_approval)
    print(f"\nFinal Result: {result}")

    # Final Verification
    try:
        # Need to reload because the file was written to disk
        import importlib

        import calc
        importlib.reload(calc)
        assert calc.calculate_sum(2, 3) == 5
        print("✨ Final Verification Passed: calculate_sum(2, 3) == 5")
    except Exception as e:
        print(f"❌ Final Verification Failed: {e}")

if __name__ == "__main__":
    main()
