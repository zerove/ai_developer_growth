# Knowledge Link Auditor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement `tools/scripts/link_auditor.py` to audit Markdown files for broken `[[path|title]]` links and generate a report.

**Architecture:**
- Use `re` to find all `[[...|...]]` patterns in `.md` files under `docs/`.
- Validate path existence relative to the repository root.
- CLI output report of broken links.

**Tech Stack:**
- Python 3.9+
- `re` (regex)
- `os` (filesystem)
- `unittest`

## Global Constraints
- **Must** scan only `.md` files.
- **Must** handle relative paths correctly.
- **Must** report clearly which file contains the broken link.

---

### Task 1: Link Extractor & Broken Link Validator

**Files:**
- Create: `tools/scripts/link_auditor.py`
- Test: `tests/test_link_auditor.py`

**Interfaces:**
- Consumes: Directory path to scan.
- Produces: List of `(file_path, broken_link_path)`.

- [x] **Step 1: Write the failing test**

```python
import unittest
import os
from tools.scripts.link_auditor import find_broken_links

class TestLinkAuditor(unittest.TestCase):
    def setUp(self):
        self.test_dir = "test_docs"
        os.makedirs(self.test_dir, exist_ok=True)
        # Create a valid file
        with open(os.path.join(self.test_dir, "valid.md"), "w") as f:
            f.write("content")
        # Create a file with broken link
        with open(os.path.join(self.test_dir, "broken.md"), "w") as f:
            f.write("[[nonexistent.md|Title]]")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.test_dir)

    def test_find_broken_links(self):
        broken = find_broken_links(self.test_dir)
        self.assertEqual(len(broken), 1)
        self.assertEqual(broken[0][0], os.path.join(self.test_dir, "broken.md"))
        self.assertEqual(broken[0][1], "nonexistent.md")

if __name__ == "__main__":
    unittest.main()
```

- [x] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests/test_link_auditor.py`
Expected: FAIL (ImportError or module not found)

- [x] **Step 3: Write minimal implementation**

```python
import re
import os

def find_broken_links(directory):
    broken_links = []
    link_pattern = re.compile(r"\[\[(.*?)\|(.*?)\]\]")
    
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(".md"):
                file_path = os.path.join(root, file)
                with open(file_path, "r") as f:
                    content = f.read()
                    for match in link_pattern.finditer(content):
                        target_path = match.group(1)
                        if not os.path.exists(os.path.join(root, target_path)):
                            broken_links.append((file_path, target_path))
    return broken_links
```

- [x] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests/test_link_auditor.py`
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add tools/scripts/link_auditor.py tests/test_link_auditor.py
git commit -m "feat: add knowledge link auditor"
```

### Task 2: CLI Wrapper

**Files:**
- Modify: `tools/scripts/link_auditor.py`

**Interfaces:**
- Consumes: Command line arguments.
- Produces: Printed report.

- [x] **Step 1: Add CLI interface**

```python
import sys
# ... existing imports

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python link_auditor.py <directory>")
        sys.exit(1)
        
    broken = find_broken_links(sys.argv[1])
    if broken:
        print("Broken links found:")
        for file, link in broken:
            print(f"  {file}: [[{link}]]")
        sys.exit(1)
    else:
        print("All links are valid.")
        sys.exit(0)
```

- [x] **Step 2: Run verification**

Run: `python3 tools/scripts/link_auditor.py test_docs`
Expected: Prints broken link info.

- [x] **Step 3: Commit**

```bash
git add tools/scripts/link_auditor.py
git commit -m "feat: add CLI for link auditor"
```
