import time


class MockLLM:
    """Simulates an LLM response based on the role and input."""

    def generate(self, role: str, prompt: str) -> str:
        # Simple mock logic to simulate different agent outputs
        if role == "PM":
            return (
                f"[PRD] Project: {prompt}\n"
                "- Goal: Create a functional tool.\n"
                "- Requirements: Input amount, select currency, output converted value.\n"  # noqa: E501
                "- Success Criteria: Accuracy and simplicity."
            )
        elif role == "Architect":
            return (
                f"[Design] Based on PRD: {prompt}\n"
                "- Component: CurrencyConverter Class\n"
                "- Method: convert(amount, from_curr, to_curr)\n"
                "- API: JSON interface {{ 'amount': float, 'from': str, 'to': str }}"  # noqa: E501
                " -> {{ 'result': float }}"
            )
        elif role == "Coder":
            if "FIX" in prompt:
                return (
                    "def convert(amount, from_curr, to_curr):\n"
                    "    # Fixed: Added error handling\n"
                    "    try:\n"
                    "        rate = 1.1 # Mock rate\n"
                    "        return amount * rate\n"
                    "    except Exception as e:\n"
                    "        return str(e)"
                )
            return (
                "def convert(amount, from_curr, to_curr):\n"
                "    rate = 1.1 # Mock rate\n"
                "    return amount * rate"
            )
        elif role == "Reviewer":
            if "error handling" in prompt:
                return "PASS: Code looks good now."
            return "FAIL: Missing error handling for invalid inputs."
        return "I don't know how to handle this."


class Agent:
    def __init__(self, role: str, llm: MockLLM):
        self.role = role
        self.llm = llm

    def run(self, input_text: str) -> str:
        print(f"[{self.role}] is processing...")
        time.sleep(0.5)  # Simulate thinking
        return self.llm.generate(self.role, input_text)


class WorkflowOrchestrator:
    def __init__(self):
        self.llm = MockLLM()
        self.pm = Agent("PM", self.llm)
        self.architect = Agent("Architect", self.llm)
        self.coder = Agent("Coder", self.llm)
        self.reviewer = Agent("Reviewer", self.llm)

    def execute(self, request: str):
        print(f"🚀 Starting Workflow for: {request}\n" + "=" * 50)

        # 1. PM Phase
        prd = self.pm.run(request)
        print(f"📄 PM Output:\n{prd}\n" + "-" * 30)

        # 2. Architect Phase
        design = self.architect.run(prd)
        print(f"📐 Architect Output:\n{design}\n" + "-" * 30)

        # 3. Coder & Reviewer Loop
        iteration = 1
        review_feedback = ""
        while True:
            print(f"💻 Coder Iteration {iteration}...")
            code = self.coder.run(
                design if iteration == 1 else f"FIX: {review_feedback}"
            )
            print(f"📝 Code:\n{code}\n" + "-" * 20)

            print("🔍 Reviewer is checking...")
            review_feedback = self.reviewer.run(code)
            print(f"📢 Reviewer Feedback: {review_feedback}\n" + "-" * 30)

            if "PASS" in review_feedback:
                print("✅ Review passed!")
                break

            print("❌ Review failed. Sending back to Coder...")
            iteration += 1
            if iteration > 3:
                print("⚠️ Max iterations reached. Terminating.")
                break

        print("=" * 50 + "\n🎉 Workflow Completed Successfully!")


if __name__ == "__main__":
    orchestrator = WorkflowOrchestrator()
    orchestrator.execute("Build a simple currency converter")
