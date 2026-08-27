from __future__ import annotations

import argparse

from ._shared import (
    Path,
    check_directory,
    check_file,
    detect_language,
    load_framework_rules,
    load_rules_for_language,
)


def cmd_html_report(args: argparse.Namespace) -> int:
    """Generate HTML quality gate report."""
    from tools.report import save_html_report

    target = Path(args.path).resolve()
    detected = detect_language(target)
    language = args.lang or detected.get("language", "unknown")
    framework = detected.get("framework")

    rules = load_rules_for_language(language)
    if framework:
        fw_rules = load_framework_rules(framework)
        rules["anti_patterns"].extend(fw_rules.get("anti_patterns", []))

    if target.is_file():
        issues = check_file(target, rules)
        files_checked = 1
    else:
        issues = check_directory(target, rules)
        files_checked = len(set(i.file for i in issues))

    output_path = save_html_report(issues, args.output, language, framework, files_checked)
    print(f"HTML report saved to: {output_path}")
    print(f"  Language: {language}")
    print(f"  Issues: {len(issues)}")
    return 0
