#!/usr/bin/env python3
"""
ADG - AI Developer Governance CLI

Checks code against language-specific anti-pattern rules, security patterns,
and quality standards. Self-contained - no external dependencies beyond PyYAML.

Usage:
    adg check <path>                    # auto-detect language, check all
    adg check <path> --lang python      # force language
    adg check <path> --severity error   # only errors
    adg detect <path>                   # detect project language
    adg list-rules --lang <lang>        # list rules for language
    adg install-hooks [path]            # install pre-commit hook
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# ──────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────

_ADG_HOME = Path(os.environ.get("ADG_HOME", Path.home() / ".config" / "adg"))
_RULES_PATH = _ADG_HOME / "rules"

# Fallback: check if ai_developer_growth source is available
_ADG_SOURCE = Path.home() / "dev" / "ai_developer_growth" / "ai-dev-framework"

def _get_rules_path() -> Path:
    """Get the rules directory, preferring config, falling back to source."""
    if _RULES_PATH.exists() and (_RULES_PATH / "languages").exists():
        return _RULES_PATH
    if _ADG_SOURCE.exists():
        return _ADG_SOURCE
    print(f"Error: Rules not found at {_RULES_PATH} or {_ADG_SOURCE}", file=sys.stderr)
    sys.exit(1)

# ──────────────────────────────────────────────────────────
# Language Detection
# ──────────────────────────────────────────────────────────

EXTENSION_MAP: dict[str, str] = {
    ".py": "python", ".pyi": "python",
    ".ts": "typescript", ".tsx": "typescript",
    ".js": "javascript", ".jsx": "javascript", ".mjs": "javascript",
    ".rs": "rust",
    ".go": "go",
    ".java": "java",
    ".kt": "kotlin", ".kts": "kotlin",
    ".cs": "csharp",
    ".php": "php",
    ".rb": "ruby",
    ".cpp": "cpp", ".cc": "cpp", ".hpp": "cpp", ".h": "cpp",
    ".swift": "swift",
    ".dart": "dart",
    ".scala": "scala",
    ".clj": "clojure",
    ".ex": "elixir", ".exs": "elixir",
    ".hs": "haskell",
    ".zig": "zig",
    ".lua": "lua",
    ".r": "r", ".R": "r",
    ".ps1": "powershell",
    ".pl": "perl", ".pm": "perl",
    ".asm": "assembly", ".s": "assembly", ".S": "assembly",
    ".f90": "fortran", ".f": "fortran",
    ".graphql": "graphql", ".gql": "graphql",
}

CONFIG_MARKERS: dict[tuple[str, str | None]] = {
    "pyproject.toml": "python", "setup.py": "python", "requirements.txt": "python",
    "Cargo.toml": "rust", "go.mod": "go",
    "package.json": None,  # could be JS or TS
    "tsconfig.json": "typescript",
    "pom.xml": "java", "build.gradle": "java", "build.gradle.kts": "kotlin",
    "Gemfile": "ruby", "composer.json": "php",
    "CMakeLists.txt": "cpp", "build.sbt": "scala",
}

FRAMEWORK_SIGNATURES: dict[str, list[str]] = {
    # JavaScript/TypeScript frameworks (order matters for detection)
    "nextjs": ["next", "nextjs"],
    "react": ["react", "react-dom"],
    "vue": ["vue", "nuxt"],
    "angular": ["@angular/core"],
    "express": ["express"],
    "nestjs": ["@nestjs/core"],
    # Python frameworks
    "fastapi": ["fastapi"],
    "django": ["django"],
    "flask": ["flask"],
    # Go frameworks
    "gin": ["github.com/gin-gonic/gin"],
    # Rust frameworks
    "actix": ["actix-web"],
    "axum": ["axum"],
    # Java frameworks
    "spring-boot": ["spring-boot"],
    "spring": ["spring"],
}

SKIP_DIRS = {
    ".git", ".svn", "node_modules", "target", "vendor", "__pycache__",
    ".venv", "venv", "dist", "build", ".tox", ".mypy_cache", ".ruff_cache",
    ".pytest_cache", "coverage", ".next", ".nuxt",
    # Generated documentation / build output
    "book", "site", "_build", "out", "public", "static",
    # IDE / editor
    ".idea", ".vscode", ".vs", "*.swp",
    # Cache directories
    ".cache", "tmp", ".tmp",
}

MAX_FILES = 5000

# Skip generated/minified files
SKIP_EXTENSIONS = {
    ".min.js", ".min.css", ".map", ".lock", ".sum",
    ".pyc", ".pyo", ".class", ".o", ".so", ".dll",
    ".exe", ".bin", ".dat", ".db",
}


def detect_language(dirpath: Path) -> dict[str, Any]:
    """Detect primary language and framework of a project."""
    result: dict[str, Any] = {
        "language": "unknown", "framework": None, "confidence": 0.0
    }

    # 1. Check config files
    for config_file, lang in CONFIG_MARKERS.items():
        if (dirpath / config_file).exists():
            if config_file == "package.json":
                lang = "typescript" if (dirpath / "tsconfig.json").exists() else "javascript"
            result["language"] = lang or "unknown"
            result["confidence"] = 0.9
            result["framework"] = _detect_framework(dirpath, lang)
            return result

    # 2. Count file extensions
    counter: Counter[str] = Counter()
    count = 0
    for filepath in dirpath.rglob("*"):
        if count >= MAX_FILES:
            break
        if not filepath.is_file():
            continue
        if any(part in SKIP_DIRS for part in filepath.parts):
            continue
        suffix = filepath.suffix.lower()
        if suffix in EXTENSION_MAP:
            counter[EXTENSION_MAP[suffix]] += 1
            count += 1

    if not counter:
        return result

    total = sum(counter.values())
    primary, primary_count = counter.most_common(1)[0]
    result["language"] = primary
    result["confidence"] = round(primary_count / total, 2)
    result["framework"] = _detect_framework(dirpath, primary)
    return result


def _detect_framework(dirpath: Path, language: str | None) -> str | None:
    """Detect framework from project config files."""
    # Check package.json
    pkg_path = dirpath / "package.json"
    if pkg_path.exists():
        try:
            pkg = json.loads(pkg_path.read_text(encoding="utf-8"))
            all_deps: dict[str, str] = {}
            for key in ("dependencies", "devDependencies"):
                if key in pkg and isinstance(pkg[key], dict):
                    all_deps.update(pkg[key])
            for framework, signatures in FRAMEWORK_SIGNATURES.items():
                if any(sig in all_deps for sig in signatures):
                    return framework
        except (OSError, json.JSONDecodeError):
            pass

    # Check Python requirements
    for req_file in ("requirements.txt", "pyproject.toml"):
        req_path = dirpath / req_file
        if req_path.exists():
            try:
                content = req_path.read_text(encoding="utf-8").lower()
                for framework, signatures in FRAMEWORK_SIGNATURES.items():
                    if any(sig.lower() in content for sig in signatures):
                        return framework
            except OSError:
                pass

    # Check for manage.py (Django indicator)
    if (dirpath / "manage.py").exists():
        try:
            content = (dirpath / "manage.py").read_text(encoding="utf-8")
            if "django" in content.lower():
                return "django"
        except OSError:
            pass

    # Check for settings.py in common Django locations
    for settings_path in ["settings.py", "config/settings.py", "myproject/settings.py"]:
        if (dirpath / settings_path).exists():
            return "django"

    # Check go.mod
    go_mod = dirpath / "go.mod"
    if go_mod.exists():
        try:
            content = go_mod.read_text(encoding="utf-8")
            for framework, signatures in FRAMEWORK_SIGNATURES.items():
                if any(sig in content for sig in signatures):
                    return framework
        except OSError:
            pass

    # Check Java build files (pom.xml, build.gradle)
    for build_file in ("pom.xml", "build.gradle", "build.gradle.kts"):
        build_path = dirpath / build_file
        if build_path.exists():
            try:
                content = build_path.read_text(encoding="utf-8")
                if "spring" in content.lower():
                    return "spring"
            except OSError:
                pass

    # Check Rust Cargo.toml
    cargo_toml = dirpath / "Cargo.toml"
    if cargo_toml.exists():
        try:
            content = cargo_toml.read_text(encoding="utf-8").lower()
            for framework, signatures in FRAMEWORK_SIGNATURES.items():
                if any(sig.lower() in content for sig in signatures):
                    return framework
        except OSError:
            pass

    return None


def _detect_language_from_file(filepath: Path) -> str | None:
    """Detect language from a single file extension."""
    return EXTENSION_MAP.get(filepath.suffix.lower())


# ──────────────────────────────────────────────────────────
# Rule Loading
# ──────────────────────────────────────────────────────────

def _load_yaml(path: Path) -> dict[str, Any]:
    """Load YAML file. Tries PyYAML first, falls back to simple parser."""
    try:
        import yaml
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except ImportError:
        return _simple_yaml_parse(path)
    except Exception:
        return {}


def _simple_yaml_parse(path: Path) -> dict[str, Any]:
    """Minimal YAML parser for anti_patterns.yml files (no PyYAML needed)."""
    content = path.read_text(encoding="utf-8")
    result: dict[str, Any] = {"anti_patterns": []}
    current_rule: dict[str, Any] | None = None

    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        # Anti-pattern list item (check BEFORE top-level keys)
        if stripped.startswith("- id:"):
            if current_rule:
                result["anti_patterns"].append(current_rule)
            current_rule = {"id": stripped.split(":", 1)[1].strip()}
            continue

        # Top-level keys (only lines NOT starting with space and NOT starting with -)
        if not line.startswith(" ") and not line.startswith("-") and ":" in stripped:
            key, _, val = stripped.partition(":")
            val = val.strip().strip("'\"")
            if key == "language":
                result["language"] = val
            elif key == "version":
                result["version"] = val
            continue

        # Rule fields
        if current_rule and ":" in stripped:
            key, _, val = stripped.partition(":")
            key = key.strip()
            val = val.strip().strip("'\"")
            if key in ("name", "severity", "category", "pattern", "message", "fix_hint", "fix_replacement"):
                current_rule[key] = val
            elif key == "ignore_case" and val == "true":
                current_rule["ignore_case"] = True
            elif key == "multiline" and val == "true":
                current_rule["multiline"] = True

    if current_rule:
        result["anti_patterns"].append(current_rule)

    return result


def load_rules_for_language(language: str) -> dict[str, Any]:
    """Load anti-pattern rules for a specific language."""
    rules_path = _get_rules_path()
    lang_rules_file = rules_path / "languages" / language / "rules.d" / "anti_patterns.yml"

    lang_rules: dict[str, Any] = {"anti_patterns": []}
    if lang_rules_file.exists():
        lang_rules = _load_yaml(lang_rules_file)

    # Load cross-language security rules
    security_file = rules_path / "common" / "security.yml"
    security_rules: dict[str, Any] = {"anti_patterns": []}
    if security_file.exists():
        security_rules = _load_yaml(security_file)

    # Merge: language-specific + security
    all_patterns = lang_rules.get("anti_patterns", []) + security_rules.get("anti_patterns", [])
    return {"anti_patterns": all_patterns, "language": language}


def load_framework_rules(framework: str) -> dict[str, Any]:
    """Load anti-pattern rules for a specific framework."""
    rules_path = _get_rules_path()
    fw_rules_file = rules_path / "frameworks" / framework / "rules.d" / "anti_patterns.yml"

    if fw_rules_file.exists():
        return _load_yaml(fw_rules_file)
    return {"anti_patterns": []}


# ──────────────────────────────────────────────────────────
# Code Checking
# ──────────────────────────────────────────────────────────

@dataclass
class Issue:
    rule_id: str
    severity: str
    category: str
    file: str
    line: int
    column: int
    message: str
    fix_hint: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "severity": self.severity,
            "category": self.category,
            "file": self.file,
            "line": self.line,
            "column": self.column,
            "message": self.message,
            "fix_hint": self.fix_hint,
        }


def check_file(filepath: Path, rules: dict[str, Any], severity_filter: str | None = None) -> list[Issue]:
    """Check a single file against rules."""
    issues: list[Issue] = []

    if not filepath.exists() or filepath.stat().st_size == 0:
        return issues

    # Skip generated/minified files
    if filepath.suffix in SKIP_EXTENSIONS or filepath.name.endswith(".min.js"):
        return issues

    try:
        content = filepath.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return issues

    lines = content.split("\n")

    for pattern_def in rules.get("anti_patterns", []):
        severity = pattern_def.get("severity", "warning")
        if severity_filter and _severity_rank(severity) > _severity_rank(severity_filter):
            continue

        issues.extend(_check_pattern(filepath, content, lines, pattern_def))

    return issues


def _severity_rank(severity: str) -> int:
    """Return numeric rank for severity comparison."""
    return {"error": 0, "warning": 1, "info": 2}.get(severity, 3)


def _check_pattern(filepath: Path, content: str, lines: list[str], pattern_def: dict[str, Any]) -> list[Issue]:
    """Check a single pattern against file content."""
    issues: list[Issue] = []
    pattern = pattern_def.get("pattern", "")
    if not pattern:
        return issues

    # Check exclude patterns
    for exclude in pattern_def.get("exclude_patterns", []):
        if re.search(exclude, content):
            return []

    flags = re.IGNORECASE if pattern_def.get("ignore_case", False) else 0
    is_multiline = ("\n" in pattern or "\\n" in pattern) or pattern_def.get("multiline", False)

    if is_multiline:
        try:
            for match in re.finditer(pattern, content, flags | re.MULTILINE):
                line_num = content[: match.start()].count("\n") + 1
                issues.append(_make_issue(filepath, line_num, 0, pattern_def))
        except re.error:
            pass
    else:
        for line_num, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith("//"):
                continue
            try:
                for match in re.finditer(pattern, line, flags):
                    issues.append(_make_issue(filepath, line_num, match.start() + 1, pattern_def))
            except re.error:
                continue

    return issues


def _make_issue(filepath: Path, line: int, column: int, pattern_def: dict[str, Any]) -> Issue:
    """Create an Issue from a pattern definition."""
    return Issue(
        rule_id=pattern_def.get("id", "unknown"),
        severity=pattern_def.get("severity", "warning"),
        category=pattern_def.get("category", "anti-pattern"),
        file=str(filepath),
        line=line,
        column=column,
        message=pattern_def.get("message", "Anti-pattern detected"),
        fix_hint=pattern_def.get("fix_hint", ""),
    )


def check_directory(dirpath: Path, rules: dict[str, Any], severity_filter: str | None = None) -> list[Issue]:
    """Check all code files in a directory."""
    all_issues: list[Issue] = []

    for filepath in dirpath.rglob("*"):
        if not filepath.is_file():
            continue
        if any(part in SKIP_DIRS for part in filepath.parts):
            continue
        if filepath.suffix in SKIP_EXTENSIONS:
            continue
        lang = _detect_language_from_file(filepath)
        if lang:
            all_issues.extend(check_file(filepath, rules, severity_filter))

    return all_issues


# ──────────────────────────────────────────────────────────
# Output Formatting
# ──────────────────────────────────────────────────────────

_SEVERITY_COLORS = {"error": "\033[91m", "warning": "\033[93m", "info": "\033[96m"}
_RESET = "\033[0m"


def _format_human(issues: list[Issue], language: str, framework: str | None, files_checked: int) -> str:
    """Format issues as human-readable output."""
    lines: list[str] = []

    fw_str = f" + {framework}" if framework else ""
    lines.append(f"Language: {language}{fw_str} (auto-detected)")
    lines.append(f"Rules loaded: {len(issues)} issues found")
    lines.append("")

    # Group by file
    by_file: dict[str, list[Issue]] = {}
    for issue in issues:
        by_file.setdefault(issue.file, []).append(issue)

    for filepath, file_issues in sorted(by_file.items()):
        for issue in sorted(file_issues, key=lambda i: i.line):
            color = _SEVERITY_COLORS.get(issue.severity, "")
            loc = f"{issue.file}:{issue.line}:{issue.column}"
            lines.append(f"{loc}  {color}{issue.severity:7s}{_RESET}  {issue.rule_id:30s}  {issue.message}")
            if issue.fix_hint:
                lines.append(f"{' ' * len(loc)}  {' ' * 7}  {' ' * 30}  → {issue.fix_hint}")

    # Summary
    error_count = sum(1 for i in issues if i.severity == "error")
    warning_count = sum(1 for i in issues if i.severity == "warning")
    info_count = sum(1 for i in issues if i.severity == "info")

    lines.append("")
    parts = []
    if error_count:
        parts.append(f"\033[91m{error_count} error{'s' if error_count != 1 else ''}\033[0m")
    if warning_count:
        parts.append(f"\033[93m{warning_count} warning{'s' if warning_count != 1 else ''}\033[0m")
    if info_count:
        parts.append(f"\033[96m{info_count} info\033[0m")

    if parts:
        lines.append(f"{'  '.join(parts)} in {files_checked} file{'s' if files_checked != 1 else ''}")
    else:
        lines.append(f"\033[92m✓ All checks passed\033[0m ({files_checked} files)")

    return "\n".join(lines)


def _format_json(issues: list[Issue], language: str, framework: str | None, files_checked: int) -> str:
    """Format issues as JSON output."""
    error_count = sum(1 for i in issues if i.severity == "error")
    warning_count = sum(1 for i in issues if i.severity == "warning")
    info_count = sum(1 for i in issues if i.severity == "info")

    return json.dumps({
        "language": language,
        "framework": framework,
        "files_checked": files_checked,
        "issues": [i.to_dict() for i in issues],
        "summary": {"error": error_count, "warning": warning_count, "info": info_count},
    }, indent=2, ensure_ascii=False)


# ──────────────────────────────────────────────────────────
# Commands
# ──────────────────────────────────────────────────────────

def cmd_check(args: argparse.Namespace) -> int:
    """Check code against rules."""
    target = Path(args.path).resolve()

    # Collect files to check
    if target.is_file():
        files = [target]
        detected = detect_language(target.parent)
    else:
        files = []
        for fp in target.rglob("*"):
            if fp.is_file() and any(part not in SKIP_DIRS for part in fp.parts):
                if fp.suffix not in SKIP_EXTENSIONS:
                    if _detect_language_from_file(fp):
                        files.append(fp)
        detected = detect_language(target)

    language = args.lang or detected.get("language", "unknown")
    framework = getattr(args, 'framework', None) or detected.get("framework")

    if language == "unknown":
        print("Error: Could not detect language. Use --lang to specify.", file=sys.stderr)
        return 1

    # Load rules
    rules = load_rules_for_language(language)
    if framework:
        fw_rules = load_framework_rules(framework)
        rules["anti_patterns"].extend(fw_rules.get("anti_patterns", []))

    # Check files
    all_issues: list[Issue] = []
    for fp in files:
        all_issues.extend(check_file(fp, rules, args.severity))

    # Output
    if args.json:
        print(_format_json(all_issues, language, framework, len(files)))
    else:
        print(_format_human(all_issues, language, framework, len(files)))

    # Exit code: non-zero if errors found
    has_errors = any(i.severity == "error" for i in all_issues)
    return 1 if has_errors else 0


def cmd_detect(args: argparse.Namespace) -> int:
    """Detect project language and framework."""
    target = Path(args.path).resolve()
    result = detect_language(target)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"Language:  {result['language']}")
        print(f"Framework: {result.get('framework') or 'N/A'}")
        print(f"Confidence: {result['confidence']}")

    return 0


def cmd_list_rules(args: argparse.Namespace) -> int:
    """List rules for a specific language."""
    rules = load_rules_for_language(args.lang)
    patterns = rules.get("anti_patterns", [])

    if args.json:
        print(json.dumps(patterns, indent=2, ensure_ascii=False))
        return 0

    print(f"Rules for: {args.lang}")
    print(f"Total: {len(patterns)} anti-patterns\n")

    # Group by severity
    for severity in ("error", "warning", "info"):
        group = [p for p in patterns if p.get("severity") == severity]
        if group:
            color = _SEVERITY_COLORS.get(severity, "")
            print(f"{color}{'=' * 60}")
            print(f"  {severity.upper()} ({len(group)} rules)")
            print(f"{'=' * 60}{_RESET}")
            for p in group:
                print(f"  {p.get('id', 'unknown'):30s}  {p.get('name', '')}")
                if p.get("message"):
                    print(f"  {' ' * 30}  → {p['message']}")
            print()

    return 0


def cmd_report(args: argparse.Namespace) -> int:
    """Generate a quality gate report."""
    target = Path(args.path).resolve()
    if not target.exists():
        print(f"Error: Path not found: {target}", file=sys.stderr)
        return 1

    detected = detect_language(target)
    language = args.lang or detected.get("language", "unknown")
    framework = getattr(args, 'framework', None) or detected.get("framework")

    if language == "unknown":
        print("Error: Could not detect language. Use --lang to specify.", file=sys.stderr)
        return 1

    # Load rules
    rules = load_rules_for_language(language)
    if framework:
        fw_rules = load_framework_rules(framework)
        rules["anti_patterns"].extend(fw_rules.get("anti_patterns", []))

    # Collect all issues
    all_issues: list[Issue] = []
    files_checked = 0

    if target.is_file():
        all_issues = check_file(target, rules)
        files_checked = 1
    else:
        for fp in target.rglob("*"):
            if fp.is_file() and any(part not in SKIP_DIRS for part in fp.parts):
                if fp.suffix not in SKIP_EXTENSIONS:
                    if _detect_language_from_file(fp):
                        all_issues.extend(check_file(fp, rules))
                        files_checked += 1

    # Count by severity
    severity_counts = {"error": 0, "warning": 0, "info": 0}
    for issue in all_issues:
        if issue.severity in severity_counts:
            severity_counts[issue.severity] += 1

    # Count by category
    category_counts: dict[str, int] = {}
    for issue in all_issues:
        cat = issue.category or "unknown"
        category_counts[cat] = category_counts.get(cat, 0) + 1

    # Count by file
    file_counts: dict[str, int] = {}
    for issue in all_issues:
        file_counts[issue.file] = file_counts.get(issue.file, 0) + 1

    # Top files by issue count
    top_files = sorted(file_counts.items(), key=lambda x: x[1], reverse=True)[:10]

    # Determine pass/fail
    error_threshold = getattr(args, 'error_threshold', 0)
    warning_threshold = getattr(args, 'warning_threshold', -1)  # -1 = no limit
    passed = severity_counts["error"] <= error_threshold
    if warning_threshold >= 0:
        passed = passed and severity_counts["warning"] <= warning_threshold

    # Output
    if getattr(args, 'json', False):
        report = {
            "language": language,
            "framework": framework,
            "files_checked": files_checked,
            "total_issues": len(all_issues),
            "severity": severity_counts,
            "categories": category_counts,
            "top_files": [{"file": f, "issues": c} for f, c in top_files],
            "passed": passed,
        }
        print(json.dumps(report, indent=2))
    else:
        # Color
        GREEN = "\033[0;32m"
        RED = "\033[0;31m"
        YELLOW = "\033[0;33m"
        CYAN = "\033[0;36m"
        BOLD = "\033[1m"
        NC = "\033[0m"

        print(f"\n{BOLD}{CYAN}{'='*60}{NC}")
        print(f"{BOLD}{CYAN}  ADG Quality Gate Report{NC}")
        print(f"{BOLD}{CYAN}{'='*60}{NC}\n")

        print(f"{BOLD}Project:{NC} {target}")
        print(f"{BOLD}Language:{NC} {language}" + (f" + {framework}" if framework else ""))
        print(f"{BOLD}Files Checked:{NC} {files_checked}")
        print()

        print(f"{BOLD}Issues by Severity:{NC}")
        print(f"  {RED}Errors:   {severity_counts['error']}{NC}")
        print(f"  {YELLOW}Warnings: {severity_counts['warning']}{NC}")
        print(f"  Info:     {severity_counts['info']}")
        print()

        if category_counts:
            print(f"{BOLD}Issues by Category:{NC}")
            for cat, count in sorted(category_counts.items(), key=lambda x: x[1], reverse=True):
                print(f"  {cat}: {count}")
            print()

        if top_files:
            print(f"{BOLD}Top Files by Issues:{NC}")
            for filepath, count in top_files:
                print(f"  {filepath}: {count}")
            print()

        if passed:
            print(f"{GREEN}{BOLD}✅ PASSED{NC} - Quality gate met")
        else:
            print(f"{RED}{BOLD}❌ FAILED{NC} - Quality gate not met")
            if severity_counts["error"] > error_threshold:
                print(f"  Errors ({severity_counts['error']}) exceed threshold ({error_threshold})")
            if warning_threshold >= 0 and severity_counts["warning"] > warning_threshold:
                print(f"  Warnings ({severity_counts['warning']}) exceed threshold ({warning_threshold})")

    return 0 if passed else 1


def cmd_install_hooks(args: argparse.Namespace) -> int:
    """Install pre-commit hook into a project."""
    target = Path(args.path).resolve()
    git_dir = target / ".git"

    if not git_dir.exists():
        print(f"Error: Not a git repository: {target}", file=sys.stderr)
        return 1

    hooks_dir = git_dir / "hooks"
    hooks_dir.mkdir(exist_ok=True)

    hook_path = hooks_dir / "pre-commit"
    adg_hook_source = Path(__file__).parent.parent / "config" / "adg" / "hooks" / "pre-commit"

    # Try to copy from installed hooks first
    if adg_hook_source.exists():
        hook_path.write_text(adg_hook_source.read_text())
    else:
        # Write default hook
        hook_path.write_text(_DEFAULT_PRE_COMMIT_HOOK)

    hook_path.chmod(0o755)
    print(f"✅ ADG pre-commit hook installed: {hook_path}")
    print(f"   Run 'adg check .' to test manually")
    return 0


# ──────────────────────────────────────────────────────────
# Default pre-commit hook
# ──────────────────────────────────────────────────────────

_DEFAULT_PRE_COMMIT_HOOK = '''#!/bin/bash
# ADG Governance Pre-commit Hook
# Installed by: adg install-hooks

STAGED_FILES=$(git diff --cached --name-only --diff-filter=ACM)

CODE_FILES=$(echo "$STAGED_FILES" | grep -E '\\.(py|rs|ts|js|go|java|kt|rb|php|swift|dart|scala)$' || true)

if [ -z "$CODE_FILES" ]; then
    exit 0
fi

echo "🔍 ADG Governance Check..."

# Try system adg first, then python module
if command -v adg &> /dev/null; then
    adg check $CODE_FILES --severity error
elif python3 -c "import adg" 2>/dev/null; then
    python3 -m adg check $CODE_FILES --severity error
else
    echo "⚠️  adg not found. Install: cp $(dirname "$0")/adg ~/.local/bin/adg"
    exit 0
fi

EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    echo ""
    echo "❌ Governance check failed. Fix errors before commit."
    echo "   Run: adg check $CODE_FILES"
    echo "   Skip: git commit --no-verify"
    exit 1
fi

echo "✅ Governance check passed."
'''


# ──────────────────────────────────────────────────────────
# CLI Entry Point
# ──────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        prog="adg",
        description="ADG - AI Developer Governance CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command")

    # check
    check_p = sub.add_parser("check", help="Check code against rules")
    check_p.add_argument("path", help="File or directory to check")
    check_p.add_argument("--lang", help="Force language (skip auto-detection)")
    check_p.add_argument("--framework", help="Force framework (skip auto-detection)")
    check_p.add_argument("--severity", choices=["error", "warning", "info"],
                         help="Only show issues at this severity or higher")
    check_p.add_argument("--json", action="store_true", help="Output as JSON")

    # detect
    detect_p = sub.add_parser("detect", help="Detect project language/framework")
    detect_p.add_argument("path", nargs="?", default=".", help="Project directory")
    detect_p.add_argument("--json", action="store_true", help="Output as JSON")

    # list-rules
    list_p = sub.add_parser("list-rules", help="List rules for a language")
    list_p.add_argument("--lang", required=True, help="Language name")
    list_p.add_argument("--json", action="store_true", help="Output as JSON")

    # install-hooks
    install_p = sub.add_parser("install-hooks", help="Install pre-commit hook")
    install_p.add_argument("path", nargs="?", default=".", help="Project directory")

    # report
    report_p = sub.add_parser("report", help="Generate quality gate report")
    report_p.add_argument("path", help="File or directory to report on")
    report_p.add_argument("--lang", help="Force language (skip auto-detection)")
    report_p.add_argument("--framework", help="Force framework (skip auto-detection)")
    report_p.add_argument("--error-threshold", type=int, default=0,
                         help="Max errors allowed (default: 0)")
    report_p.add_argument("--warning-threshold", type=int, default=-1,
                         help="Max warnings allowed (-1 = no limit)")
    report_p.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    commands = {
        "check": cmd_check,
        "detect": cmd_detect,
        "list-rules": cmd_list_rules,
        "install-hooks": cmd_install_hooks,
        "report": cmd_report,
    }

    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
