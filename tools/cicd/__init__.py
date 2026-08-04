"""CI/CD template generator for ADG governance integration."""

from __future__ import annotations

from pathlib import Path

# ─────────────────────────────────────────────────────────────
# GitHub Actions Templates
# ─────────────────────────────────────────────────────────────

GITHUB_ACTIONS_ADG = """name: ADG Governance Check

on:
  push:
    branches: [main, master]
  pull_request:
    branches: [main, master]

permissions:
  contents: read
  security-events: write

jobs:
  governance:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install ADG
        run: pip install adg-governance

      - name: Detect Language
        id: detect
        run: |
          LANG=$(adg detect . --json | jq -r '.language')
          echo "language=$LANG" >> $GITHUB_OUTPUT

      - name: Run ADG Check
        run: adg check . --lang ${{ steps.detect.outputs.language }} --severity warning --json > adg-report.json
        continue-on-error: true

      - name: Generate SARIF
        run: adg check . --lang ${{ steps.detect.outputs.language }} --sarif > results.sarif
        continue-on-error: true

      - name: Upload SARIF to GitHub Code Scanning
        uses: github/codeql-action/upload-sarif@v3
        if: always()
        with:
          sarif_file: results.sarif

      - name: Quality Gate
        run: |
          ERRORS=$(cat adg-report.json | jq '.summary.error')
          if [ "$ERRORS" -gt 0 ]; then
            echo "❌ Quality gate failed: $ERRORS errors found"
            exit 1
          fi
          echo "✅ Quality gate passed"

      - name: Upload Report
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: adg-governance-report
          path: adg-report.json
"""

GITHUB_ACTIONS_ADG_ADVANCED = """name: ADG Advanced Governance

on:
  push:
    branches: [main, master]
  pull_request:
  schedule:
    - cron: "0 8 * * 1"  # Weekly Monday 8am

jobs:
  governance:
    strategy:
      matrix:
        language: [python, javascript, typescript, rust, go, java]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install ADG
        run: pip install adg-governance

      - name: Check ${{ matrix.language }}
        run: adg check . --lang ${{ matrix.language }} --severity warning --sarif > results-${{ matrix.language }}.sarif
        continue-on-error: true

      - name: Upload SARIF
        uses: github/codeql-action/upload-sarif@v3
        if: always()
        with:
          sarif_file: results-${{ matrix.language }}.sarif

      - name: Record Trend
        run: adg check . --lang ${{ matrix.language }} --json > /dev/null
        continue-on-error: true
"""


# ─────────────────────────────────────────────────────────────
# GitLab CI Template
# ─────────────────────────────────────────────────────────────

GITLAB_CI_ADG = """
adg-governance:
  stage: test
  image: python:3.11
  before_script:
    - pip install adg-governance
  script:
    - adg detect . --json > detect.json
    - LANG=$(cat detect.json | python -c "import sys,json; print(json.load(sys.stdin)['language'])")
    - adg check . --lang $LANG --severity warning --json > adg-report.json
    - adg check . --lang $LANG --sarif > results.sarif
  artifacts:
    paths:
      - adg-report.json
      - results.sarif
    reports:
      sast: results.sarif
  allow_failure: false
  rules:
    - if: $CI_MERGE_REQUEST_ID
    - if: $CI_COMMIT_BRANCH == "main"
"""


# ─────────────────────────────────────────────────────────────
# Jenkins Pipeline
# ─────────────────────────────────────────────────────────────

JENKINS_PIPELINE = "pipeline {\n    agent any\n\n    stages {\n        stage('ADG Governance') {\n            steps {\n                sh '''\n                    pip install adg-governance\n                    adg detect . --json > detect.json\n                    LANG=$(python -c \"import json; print(json.load(open('detect.json'))['language'])\")\n                    adg check . --lang $LANG --severity warning --json > adg-report.json\n                    adg check . --lang $LANG --sarif > results.sarif\n                '''\n            }\n            post {\n                always {\n                    archiveArtifacts artifacts: 'adg-report.json, results.sarif'\n                }\n            }\n        }\n    }\n}"


# ─────────────────────────────────────────────────────────────
# Docker Compose
# ─────────────────────────────────────────────────────────────

DOCKER_COMPOSE_ADG = """
version: "3.8"
services:
  adg:
    image: python:3.11-slim
    volumes:
      - .:/workspace
    working_dir: /workspace
    command: >
      sh -c "
        pip install adg-governance &&
        adg detect . --json > /workspace/adg-detect.json &&
        adg check . --severity warning --json > /workspace/adg-report.json &&
        adg report . --json > /workspace/adg-gate.json
      "
"""


# ─────────────────────────────────────────────────────────────
# Template Generator
# ─────────────────────────────────────────────────────────────

TEMPLATES: dict[str, str] = {
    "github": GITHUB_ACTIONS_ADG,
    "github-advanced": GITHUB_ACTIONS_ADG_ADVANCED,
    "gitlab": GITLAB_CI_ADG,
    "jenkins": JENKINS_PIPELINE,
    "docker": DOCKER_COMPOSE_ADG,
}


def list_templates() -> list[str]:
    """List available CI/CD templates."""
    return list(TEMPLATES.keys())


def get_template(name: str) -> str | None:
    """Get a template by name."""
    return TEMPLATES.get(name)


def generate_ci_config(
    platform: str,
    output_dir: str | Path | None = None,
) -> str:
    """Generate CI/CD configuration for a platform.

    Args:
        platform: One of 'github', 'github-advanced', 'gitlab', 'jenkins', 'docker'
        output_dir: Directory to write the config file

    Returns:
        The generated config content
    """
    template = TEMPLATES.get(platform)
    if not template:
        raise ValueError(f"Unknown platform: {platform}. Available: {list_templates()}")

    if output_dir:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        filenames = {
            "github": ".github/workflows/adg-governance.yml",
            "github-advanced": ".github/workflows/adg-governance-advanced.yml",
            "gitlab": ".gitlab-ci.yml",
            "jenkins": "Jenkinsfile",
            "docker": "docker-compose.adg.yml",
        }

        filename = filenames.get(platform, f"adg-{platform}.yml")
        filepath = output_path / filename
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_text(template.strip() + "\n")

    return template.strip()


def format_template_info() -> str:
    """Format template information for display."""
    lines = [
        "ADG CI/CD Templates",
        "=" * 40,
        "",
    ]

    for name, content in TEMPLATES.items():
        lines.append(f"  {name:20s} - {content.count(chr(10))} lines")
    lines.extend(
        [
            "",
            "Usage:",
            "  adg-cicd generate github --output ./project",
            "  adg-cicd generate gitlab --output ./project",
            "",
        ]
    )

    return "\n".join(lines)
