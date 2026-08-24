"""AI hallucination pattern detector for code review.

Detects common patterns in AI-generated code that may indicate
hallucinated implementations, incorrect API usage, or unsafe patterns.

Usage:
    from tools.scripts.rules_engine.hallucination_detector import detect_hallucinations

    results = detect_hallucinations(Path("src/"))
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class HallucinationFinding:
    """A single hallucination risk finding."""

    file: str
    line: int
    column: int
    pattern_id: str
    severity: str  # "high", "medium", "low"
    category: str  # "api-misuse", "hallucinated-api", "unsafe-pattern", "logic-error"
    message: str
    evidence: str
    confidence: float  # 0.0-1.0


@dataclass
class HallucinationReport:
    """Report of hallucination analysis for a file or directory."""

    findings: list[HallucinationFinding] = field(default_factory=list)
    files_scanned: int = 0
    total_findings: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0

    def __post_init__(self) -> None:
        self._recount()

    def _recount(self) -> None:
        """Recompute aggregate counts from findings list."""
        self.total_findings = len(self.findings)
        self.high_count = sum(1 for f in self.findings if f.severity == "high")
        self.medium_count = sum(1 for f in self.findings if f.severity == "medium")
        self.low_count = sum(1 for f in self.findings if f.severity == "low")


# ─────────────────────────────────────────────────────────────
# Pattern definitions
# ─────────────────────────────────────────────────────────────

_HALLUCINATED_APIS: list[dict[str, str | float]] = [
    # Common hallucinated Python API patterns
    {
        "pattern": r"os\.listdir\(.*recursive.*\)",
        "id": "hallucinated-api-os-listdir-recursive",
        "severity": "high",
        "category": "hallucinated-api",
        "message": "os.listdir() does not support 'recursive' parameter. Use os.walk() or pathlib.Path.rglob()",
        "confidence": 0.95,
    },
    {
        "pattern": r"json\.load\(.*indent.*\)",
        "id": "hallucinated-api-json-load-indent",
        "severity": "medium",
        "category": "hallucinated-api",
        "message": "json.load() does not accept 'indent' parameter (that's json.dump())",
        "confidence": 0.90,
    },
    {
        "pattern": r"requests\.(get|post|put|delete)\(.*timeout\s*=\s*True\)",
        "id": "hallucinated-api-requests-timeout",
        "severity": "medium",
        "category": "api-misuse",
        "message": "requests timeout should be a number (seconds), not True",
        "confidence": 0.85,
    },
    {
        "pattern": r"\.append\(.*\bdict\b\s*\(.*\)\s*,\s*\w+\)",
        "id": "hallucinated-api-list-append-args",
        "severity": "high",
        "category": "hallucinated-api",
        "message": "list.append() takes exactly 1 argument. Did you mean list.extend()?",
        "confidence": 0.95,
    },
    {
        "pattern": r"dict\.update\(\s*\w+\s*,\s*\w+\s*\)",
        "id": "hallucinated-api-dict-update-positional",
        "severity": "medium",
        "category": "api-misuse",
        "message": "dict.update() with positional args may be incorrect. Use keyword args or a dict literal.",
        "confidence": 0.70,
    },
    # Hallucinated methods on common types
    {
        "pattern": r"\bstr\.split\(.*maxsplit.*\)",
        "id": "hallucinated-api-str-split-maxsplit",
        "severity": "low",
        "category": "api-misuse",
        "message": "str.split() uses 'maxsplit' parameter name, verify it's correct",
        "confidence": 0.50,
    },
    {
        "pattern": r"\bthreading\.\w+\.start\(\s*\)",
        "id": "hallucinated-api-threading-start",
        "severity": "low",
        "category": "logic-error",
        "message": "Thread started without join(). Verify thread lifecycle is managed.",
        "confidence": 0.40,
    },
]

_UNSAFE_PATTERNS: list[dict[str, str | float]] = [
    {
        "pattern": r"\beval\s*\(",
        "id": "unsafe-eval",
        "severity": "high",
        "category": "unsafe-pattern",
        "message": "eval call is unsafe with untrusted input. Consider ast.literal_eval() or a safe parser.",
        "confidence": 0.90,
    },
    {
        "pattern": r"\bexec\s*\(",
        "id": "unsafe-exec",
        "severity": "high",
        "category": "unsafe-pattern",
        "message": "exec call is unsafe. Consider a safer alternative.",
        "confidence": 0.90,
    },
    {
        "pattern": r"pickle\.loads?\s*\(",
        "id": "unsafe-pickle",
        "severity": "high",
        "category": "unsafe-pattern",
        "message": "pickle deserialization can execute arbitrary code. Use json or msgpack for untrusted data.",
        "confidence": 0.85,
    },
    {
        "pattern": r"subprocess\.call\s*\(\s*f[\"']",
        "id": "unsafe-shell-interpolation",
        "severity": "high",
        "category": "unsafe-pattern",
        "message": "f-string in subprocess.call() may cause command injection. Use list args or shlex.quote().",
        "confidence": 0.90,
    },
    {
        "pattern": r"subprocess\.call\s*\(\s*[\"'].*\{",
        "id": "unsafe-shell-format",
        "severity": "high",
        "category": "unsafe-pattern",
        "message": "String formatting in subprocess may cause command injection.",
        "confidence": 0.85,
    },
    {
        "pattern": r"os\.system\s*\(",
        "id": "unsafe-os-system",
        "severity": "medium",
        "category": "unsafe-pattern",
        "message": "os.system() is unsafe. Use subprocess.run() with shell=False.",
        "confidence": 0.80,
    },
    {
        "pattern": r"[Yy][Aa][Mm][Ll]\.load\s*\(\s*\w+\s*\)(?!\s*,\s*Loader)",
        "id": "unsafe-yaml-load",
        "severity": "high",
        "category": "unsafe-pattern",
        "message": "yaml.load() without Loader is unsafe. Use yaml.safe_load() or specify Loader=yaml.SafeLoader.",
        "confidence": 0.95,
    },
    {
        "pattern": r"\.format\s*\(.*\brequest\b",
        "id": "potential-sql-injection",
        "severity": "medium",
        "category": "unsafe-pattern",
        "message": "String formatting with request data in SQL-like context may cause injection.",
        "confidence": 0.50,
    },
]

_LOGIC_HALLUCINATIONS: list[dict[str, str | float]] = [
    # Common AI logic errors
    {
        "pattern": r"if\s+\w+\s*:\s*pass\s*$",
        "id": "logic-empty-if",
        "severity": "low",
        "category": "logic-error",
        "message": "Empty if-block with pass. Likely missing implementation.",
        "confidence": 0.60,
    },
    {
        "pattern": r"return\s+None\s*#\s*(?:TODO|FIXME|HACK|XXX)",
        "id": "logic-todo-return-none",
        "severity": "medium",
        "category": "logic-error",
        "message": "Function returns None with TODO comment. Likely incomplete implementation.",
        "confidence": 0.75,
    },
    {
        "pattern": r"except\s+\w+.*:\s*pass\s*$",
        "id": "logic-silenced-error",
        "severity": "medium",
        "category": "logic-error",
        "message": "Exception silently swallowed. At minimum, log the exception.",
        "confidence": 0.80,
    },
    {
        "pattern": r"==\s*True\b",
        "id": "logic-redundant-bool-compare",
        "severity": "low",
        "category": "logic-error",
        "message": "Redundant comparison with True. Use 'if value:' instead of 'if value == True:'.",
        "confidence": 0.85,
    },
    {
        "pattern": r"==\s*False\b",
        "id": "logic-redundant-false-compare",
        "severity": "low",
        "category": "logic-error",
        "message": "Redundant comparison with False. Use 'if not value:' instead.",
        "confidence": 0.85,
    },
    {
        "pattern": r"if\s+len\(\w+\)\s*>\s*0\b",
        "id": "logic-redundant-len-check",
        "severity": "low",
        "category": "logic-error",
        "message": "Redundant length check. Use 'if my_list:' instead of 'if len(my_list) > 0:'.",
        "confidence": 0.85,
    },
    {
        "pattern": r"if\s+len\(\w+\)\s*==\s*0\b",
        "id": "logic-redundant-empty-check",
        "severity": "low",
        "category": "logic-error",
        "message": "Redundant empty check. Use 'if not my_list:' instead of 'if len(my_list) == 0:'.",
        "confidence": 0.85,
    },
]

_IGNORE_FILES = {
    "fix_heuristics.py",
    "auto_fix.py",
    "hallucination_detector.py",
    "anti_pattern_checker.py",
    "security_patterns.py",
}

_IGNORE_DIRS = {"rules.d", "anti_patterns", ".git", "__pycache__", "node_modules"}


def _should_ignore_file(filepath: Path) -> bool:
    """Check if file should be ignored in hallucination scanning."""
    # Check by filename
    if filepath.name in _IGNORE_FILES:
        return True
    # Check by directory path
    parts = filepath.parts
    return any(part in _IGNORE_DIRS for part in parts)


_ALL_PATTERNS = _HALLUCINATED_APIS + _UNSAFE_PATTERNS + _LOGIC_HALLUCINATIONS


def _is_in_string(line: str, pos: int) -> bool:
    """Check if position is inside a string literal."""
    in_str = False
    str_char = None
    i = 0
    while i < pos and i < len(line):
        ch = line[i]
        if in_str:
            if ch == "\\":
                i += 2
                continue
            if ch == str_char:
                in_str = False
                str_char = None
        else:
            if ch in ('"', "'"):
                in_str = True
                str_char = ch
        i += 1
    return in_str


def _is_comment(line: str, pos: int) -> bool:
    """Check if position is inside a comment."""
    stripped = line.lstrip()
    if stripped.startswith("#"):
        return True
    # Check for // style comments (JS/TS/Java/C)
    for i, ch in enumerate(line):
        if i >= pos:
            break
        if ch in ('"', "'"):
            # Skip string contents
            end = line.find(ch, i + 1)
            if end != -1:
                i = end + 1
                continue
        if ch == "/" and i + 1 < len(line) and line[i + 1] == "/":
            return pos > i
    return False


def _create_finding(
    filepath: Path,
    line_num: int,
    pos: int,
    pattern_def: dict[str, Any],
    line: str,
) -> HallucinationFinding:
    """Create a hallucination finding."""
    return HallucinationFinding(
        file=str(filepath),
        line=line_num,
        column=pos,
        pattern_id=str(pattern_def["id"]),
        severity=str(pattern_def["severity"]),
        category=str(pattern_def["category"]),
        message=str(pattern_def["message"]),
        evidence=line.strip(),
        confidence=float(pattern_def["confidence"]),
    )


def _scan_line_for_patterns(
    line: str,
    line_num: int,
    filepath: Path,
    report: HallucinationReport,
) -> None:
    """Scan a single line for hallucination patterns."""
    for pattern_def in _ALL_PATTERNS:
        regex = pattern_def["pattern"]
        assert isinstance(regex, str)
        match = re.search(regex, line)
        if match:
            pos = match.start()
            if _is_in_string(line, pos):
                continue
            if _is_comment(line, pos):
                continue

            finding = _create_finding(filepath, line_num, pos, pattern_def, line)
            report.findings.append(finding)


def detect_hallucinations_in_file(filepath: Path) -> HallucinationReport:
    """Scan a single file for hallucination patterns.

    Args:
        filepath: Path to the file to scan.

    Returns:
        HallucinationReport with all findings.
    """
    if _should_ignore_file(filepath):
        return HallucinationReport(files_scanned=1, findings=[])

    report = HallucinationReport(files_scanned=0, findings=[])

    try:
        content = filepath.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return report

    report.files_scanned = 1
    lines = content.splitlines()

    for line_num, line in enumerate(lines, 1):
        _scan_line_for_patterns(line, line_num, filepath, report)

    report._recount()
    return report


def detect_hallucinations(dirpath: Path, languages: list[str] | None = None) -> HallucinationReport:
    """Scan a directory for hallucination patterns.

    Args:
        dirpath: Directory to scan.
        languages: Filter to these languages (None = all).

    Returns:
        Combined HallucinationReport for all files.
    """
    combined = HallucinationReport(files_scanned=0, findings=[])

    exts = {
        ".py",
        ".js",
        ".jsx",
        ".ts",
        ".tsx",
        ".rs",
        ".go",
        ".java",
        ".cs",
        ".rb",
        ".php",
    }
    ignore_dirs = {
        "node_modules",
        ".git",
        "__pycache__",
        ".venv",
        "venv",
        "dist",
        "build",
        ".cache",
    }

    files: list[Path] = []
    for ext in exts:
        files.extend(dirpath.rglob(f"*{ext}"))

    files = [f for f in files if not any(d in f.parts for d in ignore_dirs)]
    files = sorted(files)[:5000]  # Cap

    for filepath in files:
        report = detect_hallucinations_in_file(filepath)
        combined.findings.extend(report.findings)
        combined.files_scanned += report.files_scanned

    combined.total_findings = len(combined.findings)
    combined.high_count = sum(1 for f in combined.findings if f.severity == "high")
    combined.medium_count = sum(1 for f in combined.findings if f.severity == "medium")
    combined.low_count = sum(1 for f in combined.findings if f.severity == "low")

    return combined


def format_hallucination_report(report: HallucinationReport) -> str:
    """Format a hallucination report as human-readable text."""
    lines = [
        "AI Hallucination Pattern Analysis",
        "=" * 60,
        f"Files scanned: {report.files_scanned}",
        f"Total findings: {report.total_findings}",
        f"  High:   {report.high_count}",
        f"  Medium: {report.medium_count}",
        f"  Low:    {report.low_count}",
        "",
    ]

    if not report.findings:
        lines.append("✅ No hallucination patterns detected.")
        return "\n".join(lines)

    # Group by severity
    for severity in ("high", "medium", "low"):
        findings = [f for f in report.findings if f.severity == severity]
        if not findings:
            continue

        icon = {"high": "🔴", "medium": "🟡", "low": "🔵"}[severity]
        lines.append(f"\n{icon} {severity.upper()} SEVERITY ({len(findings)} findings)")
        lines.append("-" * 40)

        for finding in findings:
            lines.append(f"  {finding.file}:{finding.line} [{finding.pattern_id}]")
            lines.append(f"    {finding.message}")
            lines.append(f"    Evidence: {finding.evidence}")
            lines.append(f"    Confidence: {finding.confidence:.0%}")
            lines.append("")

    return "\n".join(lines)
