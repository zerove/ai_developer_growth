import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.prompt_loader import load_prompt


class TestPromptLoader(unittest.TestCase):
    def test_load_prompt_renders_template(self):
        # 假设存在 prompts/test/v1.yaml
        system_prompt, rendered = load_prompt("test", context={"adrs": "adr-data"})
        self.assertEqual(system_prompt, "Test system prompt")
        self.assertEqual(rendered, "Context: adr-data")


if __name__ == "__main__":
    unittest.main()
