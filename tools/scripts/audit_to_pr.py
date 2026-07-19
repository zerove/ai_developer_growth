import json
import sys

def format_audit_results(json_input: str) -> str:
    """
    Converts a JSON audit result into a formatted GitHub PR comment.
    """
    try:
        violations = json.loads(json_input)
    except json.JSONDecodeError:
        return "❌ Error: Invalid JSON input provided to audit-to-pr."

    if not violations:
        return "✨ **AI-Context-Sync Audit**: No specification violations detected. Great job!"

    # Statistics
    critical_count = sum(1 for v in violations if v['severity'] == 'Critical')
    warning_count = sum(1 for v in violations if v['severity'] == 'Warning')
    info_count = sum(1 for v in violations if v['severity'] == 'Info')

    # Header
    report = [
        "## ⚖️ AI-Context-Sync Audit Report",
        f"The automated auditor found **{len(violations)}** specification violations.",
        f"- 🔴 **Critical**: {critical_count}",
        f"- 🟡 **Warning**: {warning_count}",
        f"- 🔵 **Info**: {info_count}",
        "",
        "### 📋 Violation Details",
        "| Severity | Rule ID | Message |",
        "| :--- | :--- | :--- |"
    ]

    # Table rows
    for v in violations:
        severity_icon = "🔴" if v['severity'] == 'Critical' else "🟡" if v['severity'] == 'Warning' else "🔵"
        report.append(f"| {severity_icon} {v['severity']} | `{v['rule_id']}` | {v['message']} |")

    # Footer
    report.append("\n---\n")
    report.append("**How to resolve this?**")
    report.append("1. **Fix the code**: Align your changes with the project specifications.")
    report.append("2. **Override the rule**: If this is an intentional deviation, use `dx override <rule_id>` in your local environment and commit the change to `.ai-audit-history.json`.")

    return "\n".join(report)

if __name__ == "__main__":
    # Read JSON from stdin
    input_data = sys.stdin.read()
    if not input_data:
        print("❌ Error: No input provided to audit-to-pr.")
        sys.exit(1)
        
    print(format_audit_results(input_data))
