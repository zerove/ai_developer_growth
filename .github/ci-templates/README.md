# ADG CI/CD Integration Templates

This directory contains ready-to-use CI/CD templates for integrating ADG Governance into your pipeline.

## Available Templates

| Template | File | Platform |
|----------|------|----------|
| GitLab CI (Basic) | `gitlab-ci.yml` | GitLab CI/CD |
| GitLab CI (Advanced) | `gitlab-advanced-governance.yml` | GitLab CI/CD |
| GitHub Actions (Advanced) | `github-advanced-governance.yml` | GitHub Actions |
| Bitbucket Pipelines (Advanced) | `bitbucket-advanced-governance.yml` | Bitbucket Pipelines |
| Azure Pipelines | `azure-pipelines.yml` | Azure DevOps |
| Jenkins | `Jenkinsfile` | Jenkins |
| CircleCI | `circleci.yml` | CircleCI |

## Quick Start

### GitHub Actions (Advanced Governance)
Add to your `.github/workflows/jcode-governance.yml`:
```yaml
# Copy the contents of github-advanced-governance.yml
```

### GitLab CI (Advanced Governance)
Add to your `.gitlab-ci.yml`:
```yaml
include:
  - local: '.github/ci-templates/gitlab-advanced-governance.yml'
```

### Bitbucket Pipelines (Advanced Governance)
Add to your `bitbucket-pipelines.yml`:
```yaml
# Copy the contents of bitbucket-advanced-governance.yml
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

## Advanced Governance Features

The advanced templates include all Phase 2 features:

### Exception Manager
- Expiration checking with configurable alert days (30/14/7/3/1)
- Full approval workflow: Request → Pending → Approve/Reject/Revoke
- GitOps sync (bidirectional sync to `.jcode/exceptions.yaml`)
- Audit report generation

### Multi-language Supply Chain
- SBOM generation for Python, npm, Cargo, Go, Maven
- Vulnerability scanning
- Compliance checking with policy files
- Dependency freshness analysis
- SLSA provenance verification

### Dependency Graph Analysis
- Build dependency graph from SBOM
- Circular dependency detection (Tarjan algorithm)
- Version conflict detection
- Impact analysis for package changes
- Export formats: JSON, Graphviz DOT, Mermaid, Tree

### Policy as Code (OPA/Rego)
- Rego policy evaluation
- Combined governance data input (SBOM, deps, exceptions, supply chain)
- Policy bundles support
- PR comment integration for violations
- Fail-on-violation option

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

## Reusable Workflows (GitHub Actions)

For modular pipeline composition, reusable workflow jobs are available in `.github/workflows/jobs/`:
- `exception-manager.yml` - Exception management
- `dependency-graph.yml` - Dependency graph analysis
- `supply-chain.yml` - Multi-language supply chain
- `policy-as-code.yml` - OPA/Rego policy evaluation