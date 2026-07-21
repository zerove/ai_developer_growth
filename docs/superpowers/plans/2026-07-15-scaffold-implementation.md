---
title: dx scaffold Implementation Plan
description: > **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommen
category: 效率层
tags: ['AI', '07', 'Python', '测试', '15']
difficulty: 初级
reading_time: 10 分钟
updated: 2026-07-21
---

# dx scaffold Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement `dx scaffold <template>` to initialize project skeletons based on predefined templates in `templates/` and automatically configure `ai-context-sync`.

**Architecture:**
- Extend `examples/ai-context-sync/src/cli.py` with `typer` command `scaffold`.
- Logic resides in `cli.py` (or a helper in `src/utils.py` if complex).
- Relies on `shutil` for file operations and existing `init` logic for configuration.

**Tech Stack:**
- Python 3.9+
- Typer (CLI framework)
- Shutil/OS (Filesystem ops)

## Global Constraints
- **Must** fail gracefully if directory is non-empty.
- **Must** be idempotent where possible, or clearly refuse if existing.
- **Must** leave `CONTEXT.md` in a valid state.

---

### Task 1: Create Helper and Scaffold CLI Command

**Files:**
- Modify: `examples/ai-context-sync/src/cli.py`
- Test: `examples/ai-context-sync/tests/test_cli_scaffold.py`

**Interfaces:**
- Consumes: Existing `init()` function in `cli.py`.
- Produces: `dx scaffold` command.

- [ ] **Step 1: Create test file for scaffold**

```python
import unittest
from typer.testing import CliRunner
from products.ai_context_sync.src.cli import app
import os
import shutil

class TestCLIScaffold(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()
        self.test_dir = "test_scaffold_dir"
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
        os.makedirs(self.test_dir)
        os.chdir(self.test_dir)

    def tearDown(self):
        os.chdir("..")
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_scaffold_fails_on_non_empty_dir(self):
        with open("some_file.txt", "w") as f:
            f.write("hello")
        result = self.runner.invoke(app, ["scaffold", "nonexistent_template"])
        self.assertEqual(result.exit_code, 1)
        self.assertIn("Directory is not empty", result.stdout)

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest examples/ai-context-sync/tests/test_cli_scaffold.py`
Expected: FAIL (command not implemented)

- [ ] **Step 3: Implement scaffold command and logic in cli.py**

```python
import shutil
# ... inside cli.py

@app.command()
def scaffold(
    template: str = typer.Argument(..., help="Template name (in templates/ directory)"),
    config: str = typer.Option(".ai-sync.json", help="Path to config file")
):
    """Initialize a project from a predefined template."""
    # 1. Check if directory is empty
    if len([f for f in os.listdir('.') if f not in ['.git', '.DS_Store']]) > 0:
        typer.echo("❌ Directory is not empty. Aborting.")
        raise typer.Exit(code=1)
    
    # 2. Check if template exists
    template_path = os.path.join("..", "..", "..", "templates", template)
    if not os.path.exists(template_path):
        typer.echo(f"❌ Template '{template}' not found in templates/.")
        raise typer.Exit(code=1)
    
    # 3. Copy files
    # Simplified copy logic for demonstration
    for item in os.listdir(template_path):
        src = os.path.join(template_path, item)
        if os.path.isdir(src):
            shutil.copytree(src, item)
        else:
            shutil.copy2(src, item)
            
    # 4. Init
    init(config=config)
    
    # 5. Update CONTEXT.md
    with open("CONTEXT.md", "a") as f:
        f.write(f"\n--- Initialized from template: {template} ---\n")
    typer.echo(f"✅ Successfully scaffolded from {template}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest examples/ai-context-sync/tests/test_cli_scaffold.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add examples/ai-context-sync/src/cli.py examples/ai-context-sync/tests/test_cli_scaffold.py
git commit -m "feat: add dx scaffold command"
```
