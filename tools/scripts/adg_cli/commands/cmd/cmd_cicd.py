from __future__ import annotations

import argparse


def cmd_cicd(args: argparse.Namespace) -> int:
    """Generate CI/CD configuration files."""
    from tools.cicd import generate_ci_config

    generate_ci_config(args.platform, args.output)
    print(f"✅ Generated {args.platform} CI/CD config in: {args.output}")
    return 0
