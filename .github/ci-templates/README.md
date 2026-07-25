# ADG CI/CD Integration Templates

This directory contains ready-to-use CI/CD templates for integrating ADG Governance into your pipeline.

## Available Templates

| Template | File | Platform |
|----------|------|----------|
| GitLab CI | `gitlab-ci.yml` | GitLab CI/CD |
| Azure Pipelines | `azure-pipelines.yml` | Azure DevOps |
| Jenkins | `Jenkinsfile` | Jenkins |
| CircleCI | `circleci.yml` | CircleCI |

## Quick Start

### GitLab CI
Add to your `.gitlab-ci.yml`:
```yaml
include:
  - local: '.github/ci-templates/gitlab-ci.yml'
```

### Azure Pipelines
Add to your `azure-pipelines.yml`:
```yaml
resources:
  repositories:
    - repository: self
```

### Jenkins
Copy `Jenkinsfile` to your project root or reference it in your pipeline.

### CircleCI
Add to your `.circleci/config.yml`:
```yaml
include:
  - local: '.github/ci-templates/circleci.yml'
```

## JSON Output Format (CodeClimate Compatible)

All templates generate a JSON report compatible with CodeClimate format:

```json
{
  "summary": {
    "total_files": 42,
    "errors": 3,
    "warnings": 12,
    "info": 8,
    "passed": 35,
    "failed": 7
  },
  "results": [
    {
      "file": "src/main.py",
      "language": "python",
      "passed": false,
      "errors": 2,
      "warnings": 3,
      "issues": [...]
    }
  ]
}
```

## GitHub Actions

The PR quality report workflow (`.github/workflows/adg-quality-report.yml`) automatically:
- Runs ADG checks on every PR
- Posts a quality report as a PR comment
- Updates the comment on subsequent pushes
- Uploads the report as an artifact
- Fails the check if errors are found
