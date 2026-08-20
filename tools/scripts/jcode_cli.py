#!/usr/bin/env python3
"""
JCode CLI - AI-Native Development Workflow Command Line Interface

Main entry point for the JCode AI-Native SDLC ecosystem.
"""

import argparse
import sys
from pathlib import Path

from tools.scripts._common import get_project_root


def cmd_ai_native_workflow(args: argparse.Namespace) -> int:
    """Run the full AI-Native workflow pipeline."""
    from tools.scripts.jcode_ai_native_workflow import JCodeAINativeWorkflow

    workflow = JCodeAINativeWorkflow()
    intent = args.intent or "Feature Delivery via AI-Native SDLC"
    success = workflow.run_full_pipeline(intent)
    return 0 if success else 1


def cmd_ai_quality_gate(args: argparse.Namespace) -> int:
    """Run AI quality gate checks."""
    from tools.scripts.rules_engine import check_directory

    path = Path(args.path) if args.path else get_project_root()
    results = check_directory(path)

    # Print summary
    total_issues = sum(len(r.issues) for r in results)
    print("\n📊 AI Quality Gate Results:")
    print(f"  Files checked: {len(results)}")
    print(f"  Total issues: {total_issues}")

    if args.verbose:
        for result in results:
            if result.issues:
                print(f"\n{result.file}:")
                for issue in result.issues:
                    print(f"  Line {issue.line}: [{issue.severity}] {issue.message}")

    return 1 if total_issues > 0 else 0


def cmd_ai_pr_review(args: argparse.Namespace) -> int:
    """Run AI PR review on current changes."""
    from tools.scripts.ai_pr_reviewer import get_git_diff, review_diff

    diff = get_git_diff()
    if not diff:
        print("No changes to review.")
        return 0

    result = review_diff(diff)
    findings = result.get("findings", [])

    if findings:
        print(f"\n🔍 AI PR Review Found {len(findings)} Issues:")
        for finding in findings:
            print(f"  [{finding['category']}] {finding['rule']}: {finding['description']}")
        return 1
    else:
        print("✅ No issues found in PR review.")
        return 0


def cmd_case_quality(args: argparse.Namespace) -> int:
    """Analyze case study quality."""
    from tools.scripts.analyze_case_quality import CaseStudyQualityAnalyzer, format_report

    analyzer = CaseStudyQualityAnalyzer()

    if args.case:
        case_path = Path(args.case)
        metrics = analyzer.analyze_case(case_path)
        print(f"Case: {metrics.case_name}")
        print(f"  Overall: {metrics.overall_score:.1f}/100")
        print(f"  Authenticity: {metrics.authenticity_score:.1f}")
        print(f"  Efficiency: {metrics.efficiency_credibility:.1f}")
        print(f"  Insight: {metrics.insight_quality:.1f}")
        print(f"  Completeness: {metrics.completeness:.1f}")
        print(f"  Cross-Refs: {metrics.cross_references:.1f}")
        if metrics.issues:
            print("  Issues:")
            for issue in metrics.issues:
                print(f"    - {issue}")
        if metrics.strengths:
            print("  Strengths:")
            for strength in metrics.strengths:
                print(f"    - {strength}")
    else:
        metrics_list = analyzer.analyze_all()
        report = analyzer.generate_report(metrics_list)
        print(format_report(report))

    return 0


def cmd_validate_case_study(args: argparse.Namespace) -> int:
    """Validate case study structure."""
    from tools.scripts.validate_case_study import main as validate_main

    sys.argv = ["validate_case_study.py"] + args.rest
    return validate_main()


def cmd_create_case_study(args: argparse.Namespace) -> int:
    """Create new case study from template."""
    from tools.scripts.create_case_study import main as create_main

    sys.argv = ["create_case_study.py"] + args.rest
    create_main()
    return 0


def cmd_dor_check(args: argparse.Namespace) -> int:
    """Check Definition of Readiness."""
    from tools.scripts.dor_checker import DoRChecker

    checker = DoRChecker(get_project_root())
    intent = args.intent or "Default intent"
    result = checker.evaluate_intent(intent)

    print(f"DoR Check for: {intent}")
    print(f"  Passed: {result['passed']}")
    print(f"  Score: {result['score']}/7")
    if result.get("violations"):
        print("  Violations:")
        for v in result["violations"]:
            print(f"    - {v}")

    return 0 if result["passed"] else 1


def cmd_semantic_graph(args: argparse.Namespace) -> int:
    """Build and query semantic code graph."""
    from tools.scripts.semantic_code_graph import SemanticCodeGraph

    graph = SemanticCodeGraph(get_project_root())
    graph.build_graph()

    if args.query:
        results = graph.query_impact(args.query)
        print(f"Query: {args.query}")
        for r in results:
            print(f"  {r}")

    return 0


def cmd_arch_visualizer(args: argparse.Namespace) -> int:
    """Generate architecture visualizations."""
    from tools.scripts.arch_visualizer import generate_mermaid_diagram, scan_python_imports

    graph = scan_python_imports(get_project_root())
    mermaid = generate_mermaid_diagram(graph)

    output_path = Path(args.output) if args.output else Path("architecture.md")
    output_path.write_text(f"## Architecture Dependency Graph\n\n```mermaid\n{mermaid}\n```\n", encoding="utf-8")
    print(f"✅ Architecture visualization saved to: {output_path}")
    return 0


def cmd_metrics_telemetry(args: argparse.Namespace) -> int:
    """Collect and display metrics telemetry."""
    from tools.scripts.metrics_telemetry import MetricsTelemetry

    telemetry = MetricsTelemetry(get_project_root())
    metrics = telemetry.collect_metrics()
    print(f"Collected metrics: {metrics}")
    return 0


def cmd_audit_attestation(args: argparse.Namespace) -> int:
    """Generate audit attestation."""
    from tools.scripts.audit_attestation import AuditAttestationLedger

    ledger = AuditAttestationLedger(get_project_root())
    if args.intent:
        ledger.record_trace("MANUAL", {"intent": args.intent})
    report = ledger.generate_report()
    print(report)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="jcode",
        description="JCode AI-Native SDLC Command Line Interface",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  ai-native-workflow    Run full AI-Native workflow pipeline
  ai-quality-gate       Run AI code quality checks
  ai-pr-review          Review current git changes
  case-quality          Analyze case study quality
  validate-case         Validate case study structure
  create-case           Create new case study from template
  dor-check             Check Definition of Readiness
  semantic-graph        Build/query semantic code graph
  arch-visualizer       Generate architecture visualization
  metrics-telemetry     Collect metrics telemetry
  audit-attestation     Generate audit attestation report

Examples:
  jcode ai-native-workflow --intent "Add user authentication"
  jcode ai-quality-gate --path ./src --verbose
  jcode ai-pr-review
  jcode case-quality --case case-studies/ai-task-prioritizer.md
  jcode validate-case --path case-studies/new-case.md
  jcode create-case --title "My New Case" --category "CLI Tool"
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # ai-native-workflow
    p = subparsers.add_parser("ai-native-workflow", help="Run full AI-Native workflow")
    p.add_argument("--intent", type=str, help="Feature intent description")
    p.set_defaults(func=cmd_ai_native_workflow)

    # ai-quality-gate
    p = subparsers.add_parser("ai-quality-gate", help="Run AI quality checks")
    p.add_argument("--path", type=str, help="Path to check (default: project root)")
    p.add_argument("--verbose", "-v", action="store_true", help="Show detailed issues")
    p.set_defaults(func=cmd_ai_quality_gate)

    # ai-pr-review
    p = subparsers.add_parser("ai-pr-review", help="Review current git changes")
    p.set_defaults(func=cmd_ai_pr_review)

    # case-quality
    p = subparsers.add_parser("case-quality", help="Analyze case study quality")
    p.add_argument("--case", type=str, help="Specific case study path")
    p.set_defaults(func=cmd_case_quality)

    # validate-case
    p = subparsers.add_parser("validate-case", help="Validate case study structure")
    p.add_argument("rest", nargs=argparse.REMAINDER, help="Arguments to pass through")
    p.set_defaults(func=cmd_validate_case_study)

    # create-case
    p = subparsers.add_parser("create-case", help="Create new case study")
    p.add_argument("rest", nargs=argparse.REMAINDER, help="Arguments to pass through")
    p.set_defaults(func=cmd_create_case_study)

    # dor-check
    p = subparsers.add_parser("dor-check", help="Check Definition of Readiness")
    p.add_argument("--intent", type=str, help="Intent to validate")
    p.set_defaults(func=cmd_dor_check)

    # semantic-graph
    p = subparsers.add_parser("semantic-graph", help="Build/query semantic graph")
    p.add_argument("--query", type=str, help="Query to execute")
    p.set_defaults(func=cmd_semantic_graph)

    # arch-visualizer
    p = subparsers.add_parser("arch-visualizer", help="Generate architecture visualization")
    p.add_argument("--output", "-o", type=str, help="Output file path")
    p.set_defaults(func=cmd_arch_visualizer)

    # metrics-telemetry
    p = subparsers.add_parser("metrics-telemetry", help="Collect metrics")
    p.set_defaults(func=cmd_metrics_telemetry)

    # audit-attestation
    p = subparsers.add_parser("audit-attestation", help="Generate audit attestation")
    p.add_argument("--intent", type=str, help="Intent for audit record")
    p.set_defaults(func=cmd_audit_attestation)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    try:
        return args.func(args)  # type: ignore[no-any-return]
    except KeyboardInterrupt:
        print("\n⚠️ Interrupted by user")
        return 130
    except Exception as e:
        print(f"❌ Error: {e}")
        if args.verbose if hasattr(args, "verbose") else False:
            import traceback

            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
