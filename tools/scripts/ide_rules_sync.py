"""AI IDE Rules Synchronizer (.cursorrules & .windsurfrules)

Automatically generates or updates .cursorrules and .windsurfrules at the project root
based on GOVERNANCE.md and AGENTS.md standards, ensuring AI assistants strictly follow
project coding rules, anti-patterns, and quality gates.
"""

from __future__ import annotations

from pathlib import Path

from tools.scripts._common import get_project_root

CURSORRULES_TEMPLATE = """# AI Developer Growth - Cursor Rules & Governance Standards

## Core Principles
1. **No AI Slop / Anti-Patterns**: Never use `as any`, `@ts-ignore`, `unwrap()`, or `expect()` in production code.
2. **Quality Gates**: All changed files must pass linter, typecheck, and unit tests.
3. **Small & Focused Changes**: Small, clean, atomic changes over massive refactors.
4. **Documentation & Context**: Keep CONTEXT.md and ADRs updated when architecture decisions are made.

## Coding Standards
- Python: PEP 8, ruff, mypy strict, pytest coverage >= 80%.
- TypeScript/JavaScript: strict mode, ESLint/Prettier.
- Error Handling: Custom error types, no empty catch blocks.

## Workflow & Safety
- Never commit without explicit user request.
- Verify through actual usage/testing before claiming completion.
"""

WINDSURFRULES_TEMPLATE = """# AI Developer Growth - Windsurf Rules & Governance Standards

## System Persona
You are an expert software engineer operating within the AI Developer Growth framework.

## Directives
1. **Zero Tolerance for Type Suppression**: Prohibit `as any`, `@ts-ignore`, and unwrap/expect in production code.
2. **Modular & Clean Architecture**: Maintain single responsibility, follow existing patterns in the codebase.
3. **Thorough Verification**: Run tests and type checks after every significant modification.
4. **Context Integrity**: Respect the project context and governance guidelines outlined in GOVERNANCE.md.
"""


def generate_ide_rules(root_dir: Path | None = None) -> dict[str, Path]:
    root = root_dir or get_project_root()

    cursorrules_path = root / ".cursorrules"
    windsurfrules_path = root / ".windsurfrules"

    cursorrules_path.write_text(CURSORRULES_TEMPLATE, encoding="utf-8")
    windsurfrules_path.write_text(WINDSURFRULES_TEMPLATE, encoding="utf-8")

    return {
        "cursorrules": cursorrules_path,
        "windsurfrules": windsurfrules_path,
    }


if __name__ == "__main__":
    paths = generate_ide_rules()
    print("Successfully generated IDE rules:")
    print(f"  - {paths['cursorrules']}")
    print(f"  - {paths['windsurfrules']}")
