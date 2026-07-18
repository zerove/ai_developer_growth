# Prompt Assetization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract hardcoded LLM prompts from source code into structured, versioned YAML files and implement a loader to manage them.

**Architecture:**
- Create `products/ai_context_sync/prompts/` directory.
- Create `products/ai_context_sync/src/prompt_loader.py` to handle loading/Jinja2 templating.
- Refactor `guard.py` (and potentially others) to use the new loader.

**Tech Stack:**
- Python 3.9+
- YAML, Jinja2

## Global Constraints
- **Must** support versioning in prompt files.
- **Must** handle template variables via Jinja2 correctly.
- **Must** be fully tested with mocks.

---

### Task 1: Create Prompt Loader

**Files:**
- Create: `products/ai_context_sync/src/prompt_loader.py`
- Test: `products/ai_context_sync/tests/test_prompt_loader.py`

**Interfaces:**
- Consumes: Prompt file path, context variables.
- Produces: Formatted prompt strings.

- [ ] **Step 1: Write the failing test**

```python
import unittest
from products.ai_context_sync.src.prompt_loader import load_prompt

class TestPromptLoader(unittest.TestCase):
    def test_load_prompt_renders_template(self):
        # 假设存在 prompts/test.yaml
        prompt = load_prompt("test", context={"adrs": "adr-data"})
        self.assertIn("adr-data", prompt)

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest products/ai_context_sync/tests/test_prompt_loader.py`
Expected: FAIL (ModuleNotFoundError)

- [ ] **Step 3: Implement prompt loader**

```python
import yaml
import os
from jinja2 import Template

def load_prompt(prompt_id: str, context: dict = None, version: str = "v1"):
    # Simplified path handling
    prompt_path = os.path.join("products", "ai_context_sync", "prompts", prompt_id, f"{version}.yaml")
    
    with open(prompt_path, "r") as f:
        data = yaml.safe_load(f)
    
    template = Template(data["user_template"])
    rendered = template.render(context or {})
    return data["system_prompt"], rendered
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest products/ai_context_sync/tests/test_prompt_loader.py`
Expected: PASS

### Task 2: Refactor ArchitectureGuard to use Prompt Loader

**Files:**
- Modify: `products/ai_context_sync/src/guard.py`
- Create: `products/ai_context_sync/prompts/architecture_audit/v1.yaml`

**Interfaces:**
- Consumes: `prompt_loader.load_prompt`

- [ ] **Step 1: Create prompt asset file**

```yaml
version: "1.0.0"
system_prompt: "You are a strict Software Architecture Auditor..."
user_template: |
  ### Established ADRs
  {{adrs}}
  ### Git Diff
  {{diff}}
```

- [ ] **Step 2: Modify guard.py**

```python
from .prompt_loader import load_prompt
# ... inside check_drift_json
system_prompt, prompt = load_prompt("architecture_audit", context={"adrs": adrs, "diff": filtered_diff})
```

- [ ] **Step 3: Commit**

```bash
git add products/ai_context_sync/src/guard.py products/ai_context_sync/prompts/
git commit -m "refactor: migrate guard prompts to assetized yaml"
```
