---
title: "Tools API Reference"
description: "All scripts in tools/scripts/ share a unifie..."
category: 工具层
tags: ['AI', '开发者成长']
difficulty: 基础
---

# Tools API Reference

All scripts in `tools/scripts/` share a unified CLI interface via `rules/cli.py` and `rules/web_base.py`.

## Shared CLI Flags

Every tool supports these flags (via `rules.cli.add_common_args` or individually):

| Flag | Description |
|------|-------------|
| `--json` | Output results as JSON |
| `--format text\|json\|html\|csv` | Output format (default: text) |
| `--verbose` | Show detailed output |
| `-o, --output FILE` | Write output to file |

Error handling uses `_common.handle_error` consistently across all scripts.

---

## Core Engine

### validate_language_rules.py

The main validation engine (~2160 lines). Validates code against YAML-defined rules.

```
python validate_language_rules.py <path> --lang <language> [options]
python validate_language_rules.py <path> --auto-detect [options]
```

**Arguments:**
- `path` - File or directory to validate
- `--lang` - Language to validate against (26 languages)
- `--auto-detect` - Auto-detect language from extensions

**Options:**
- `--json` - Legacy JSON output
- `--format text|json|html|junit|sarif` - Report format
- `--fix` / `--dry-run` - Apply/show auto-fixes
- `--custom-rules DIR` - Custom .yml rules directory
- `--incremental` - Skip unchanged files
- `--changed-files FILE...` - Only check specific files
- `--linters ruff mypy eslint golangci-lint` - Run external linters
- `--health-score` - Show project health score (0-100)
- `--max-errors N` / `--max-warnings N` - Severity thresholds
- `--fail-on-warnings` - Exit 1 on warnings
- `-o FILE` - Write report to file
- `--exclude DIR...` - Directories to exclude

**Python API:**
```python
from validate_language_rules import (
    load_rules,          # Load YAML rules for a language
    load_custom_rules,   # Load .ai-rules/ custom rules
    validate_file,       # Validate a single file
    validate_directory,  # Validate a directory
    apply_fixes,         # Apply auto-fixes
    calculate_health_score,  # Compute health score (0-100)
)
```

---

## rules/ Package

### rules/models.py

Data classes for the engine.

```python
from rules.models import Issue, ValidationResult, FixResult, HealthScore

issue = Issue(
    rule_id="py-bare-except",
    severity="error",
    category="error_handling",
    file="main.py",
    line=42,
    message="Avoid bare except",
    fix_hint="Use 'except Exception:'",
)
issue.to_dict()  # -> {"rule_id": ..., "severity": ..., ...}

vr = ValidationResult(file="main.py", language="python", issues=[issue])
vr.error_count   # 1
vr.to_dict()

hs = HealthScore(score=85, grade="B", errors=1, warnings=2, infos=3, total_files=10)
hs.to_dict()
```

### rules/loader.py

Rule loading with LRU cache.

```python
from rules.loader import load_rules, load_custom_rules

# Load rules for a language (cached via @lru_cache)
rules = load_rules("python")
# -> {"anti_patterns": [...], "naming_conventions": [...], "complexity": [...]}

# Load custom rules from project
custom = load_custom_rules(Path("/my/project"))
```

### rules/cli.py

Unified CLI helpers.

```python
from rules.cli import add_common_args, output_results, cli_main

# Add standard args to your parser
parser = argparse.ArgumentParser(...)
add_common_args(parser)  # Adds --json, --format, --verbose, -o

# Output results in any format
output_results(results, fmt="json", output_file=Path("report.json"))

# Wrap main() with error handling
cli_main(my_main_fn, script_name="my_tool")
```

### rules/web_base.py

Base HTTP server for web tools.

```python
from rules.web_base import RuleWebServer, run_server

class MyHandler(RuleWebServer):
    page_title = "My Tool"

    def handle_api(self, path, query, data=None):
        if path == "/api/data":
            return {"result": "ok"}
        return {"error": "not found"}

    def get_html_content(self):
        return "<html>...</html>"

run_server(MyHandler, port=8080)
```

---

## Tools

### generate_fixes.py

Heuristic-based fix_replacement generator for rules without one.

```
python generate_fixes.py --all --dry-run
python generate_fixes.py --lang python --apply
python generate_fixes.py --all --json -o fixes.json
```

**Options:** `--lang`, `--all`, `--dry-run`, `--apply`, `-o`, `--json`, `--verbose`

### git_diff_incremental.py

Git diff integration for incremental validation.

```
python git_diff_incremental.py --ref HEAD~1
python git_diff_incremental.py --supported-only
python git_diff_incremental.py --json
```

**Options:** `--ref`, `--repo-dir`, `--supported-only`, `--json`, `--verbose`

### rule_author.py

Interactive rule creation CLI.

```
python rule_author.py init --lang mylang
python rule_author.py add-rule --lang python --category anti_patterns --id py-new-rule
python rule_author.py validate --file my-rules.yml
python rule_author.py scaffold --lang python
python rule_author.py template --category anti_patterns
```

**Subcommands:** `init`, `add-rule`, `validate`, `scaffold`, `template`

### rule_marketplace.py

Rule pack discovery and management.

```
python rule_marketplace.py list
python rule_marketplace.py search security
python rule_marketplace.py info python-pack
python rule_marketplace.py install security --project-dir /path
python rule_marketplace.py validate
python rule_marketplace.py export -o my-pack.yml
```

**Built-in packs:** security, python-pack, typescript-pack, react-pack, vue-pack, django-pack, fastapi-pack, full

### rule_registry.py

Central registry for rule packs (local ~/.ai-rules-registry/).

```
python rule_registry.py init
python rule_registry.py list
python rule_registry.py publish my-rules.yml --name my-pack
python rule_registry.py install my-pack
python rule_registry.py search security
python rule_registry.py info my-pack
python rule_registry.py remove my-pack
```

### rule_tracker.py

Rule effectiveness analytics.

```
python rule_tracker.py record --file results.json
python rule_tracker.py report --days 30
python rule_tracker.py export --format csv
python rule_tracker.py prune --keep 100
```

**Options:** `--json`, `--format`, `--verbose`

### validate_rule_tests.py

Validate YAML rule regex patterns against test_cases.

```
python validate_rule_tests.py --all
python validate_rule_tests.py --lang python
python validate_rule_tests.py --all --json
```

**Options:** `--lang`, `--all`, `--json`, `--verbose`

### rule_visualize.py

Web UI for browsing and testing rules (port 8080).

```
python rule_visualize.py
python rule_visualize.py --port 8080
```

**API endpoints:** `/api/rules`, `/api/languages`, `/api/stats`

### rule_editor.py

Live YAML editor with regex preview (port 8081).

```
python rule_editor.py
python rule_editor.py --port 8081
```

---

## Shared Module: _common.py

Common utilities used across all scripts.

```python
from _common import (
    rules_dir,           # -> Path to ai-dev-framework/
    framework_dir,       # Alias for rules_dir
    EXTENSION_MAP,       # {".py": "python", ...} (48 extensions)
    detect_language,     # Path -> language string
    file_hash,           # SHA256 content hash
    handle_error,        # Standard error handler with sys.exit
    safe_import,         # Import module safely (returns None on failure)
    load_yaml,           # Load YAML file
    save_yaml,           # Save YAML file
    filter_supported_files,  # Filter files by supported extensions
    SUPPORTED_EXTENSIONS,    # Set of supported file extensions
)
```
