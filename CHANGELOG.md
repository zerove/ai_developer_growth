# Changelog

All notable changes to the AI Developer Growth project.

## [2.1.0] - 2026-07-25

### Added

- **P0: Framework Rules Enhancement (9/9)**
  - Enhanced actix, express, nextjs, spring-boot with naming/thresholds/tooling rules
  - All 9 frameworks now have complete YAML configurations

- **P0: Auto-fix Engine**
  - `tools/scripts/rules_engine/auto_fix.py` - Regex-based auto-fix for 5 languages
  - Python: bare-except, eval, print, yaml.load, Optional syntax
  - JavaScript: eval, var, innerHTML, console.log, debugger
  - TypeScript: any type, as any, require()
  - Rust: unwrap(), panic!
  - Java: System.out.println, printStackTrace()

- **P0: CI/CD Integration Templates**
  - GitLab CI template (`.github/ci-templates/gitlab-ci.yml`)
  - GitLab MR comment integration (`.github/ci-templates/gitlab-mr-integration.yml`)
  - Azure Pipelines template (`.github/ci-templates/azure-pipelines.yml`)
  - Jenkins Pipeline template (`.github/ci-templates/Jenkinsfile`)
  - CircleCI template (`.github/ci-templates/circleci.yml`)
  - GitHub Actions PR quality report (`.github/workflows/adg-quality-report.yml`)
  - All produce CodeClimate-compatible JSON output

- **P1: Custom Rules Support**
  - `.adg/rules.yml` project-level configuration
  - `~/.config/adg/rules.yml` user global configuration
  - Priority inheritance: global → project → .ai-rules/
  - Severity override support for built-in rules
  - Example: `.adg/rules.yml.example`

- **P1: Parallel Checking**
  - `--jobs N` flag for `language-rules` and `quality-gate` commands
  - Uses `ProcessPoolExecutor` for true parallel execution
  - Auto-fallback to serial for small file sets (≤4 files)

- **P1: Pre-push Hook**
  - `adg install-hooks --pre-push` installs git pre-push hook
  - Checks unpushed commits for lint/format/language rules
  - Incremental checking of changed code files only

- **P2: Quality Dashboard**
  - `tools/scripts/rules_engine/dashboard.py` - FastAPI + SQLite web dashboard
  - Quality trend charts (errors/warnings over time)
  - File-level detail view
  - API endpoints: `/api/trend`, `/api/latest`, `/api/record`
  - Dark theme responsive UI with Chart.js
  - Run: `adg dashboard --port 8765`

- **P2: GitHub/GitLab PR Integration**
  - Auto-posts quality report as PR/MR comment
  - Updates comment on subsequent pushes
  - Fails CI on errors

- **P2: Language Extensions**
  - Enhanced Kotlin rules (10 patterns: coroutine blocking, null assertion, etc.)
  - Enhanced Swift rules (10 patterns: force unwrap, retain cycle, etc.)
  - All include naming/thresholds/tooling sections

- **P3: AI-driven Rule Generation**
  - `tools/scripts/rules_engine/ai_rules_generator.py`
  - `adg learn <project_path>` - analyzes codebase, detects 10+ pattern types
  - Generates custom `.adg/rules.yml` configuration
  - Run: `adg learn ./my-project -o .adg/rules.yml`

- **P3: LSP Server**
  - `tools/scripts/rules_engine/lsp_server.py` - IDE diagnostics via LSP
  - Real-time code quality feedback in supported editors
  - Hover: shows rule documentation
  - Code actions: quick-fix suggestions
  - Run: `python -m tools.scripts.rules_engine.lsp_server`
  - Requires: `pip install pygls`

- **Tech Debt**
  - `regex_cache.py` - Compiled regex cache for performance
  - `constants.py` - Centralized configuration constants
  - All functions have type annotations
  - All public functions have docstrings

- **Test Coverage**
  - 62 new tests across 4 test files
  - auto_fix: 30 tests (language detection, patterns, apply, format)
  - dashboard: 16 tests (DB, API, records, trends)
  - ai_rules_generator: 16 tests (detection, analysis, formatting)
  - pre_push: 5 tests (module functions, git integration)

- **CLI Integration**
  - `adg check . --fix` applies auto-fixes via language-rules command
  - hooks_runner updated with --fix flag

- **Dashboard Fixes**
  - SQLite FOREIGN KEY syntax corrected
  - Thread safety (check_same_thread=False) for FastAPI

- **Documentation**
  - Dashboard usage, API reference, CI/CD integration guide
  - AI Learn usage, detectors, output format
  - LSP Server VS Code/Neovim configuration

- **Release Notes**
  - RELEASE_v2.1.0.md with full feature summary

## [2.0.0] - 2026-07-22

### Added
- **Phase 5: Interactive Learning Platform**
  - FastAPI + Jinja2 Web UI (ai-navigation-web)
  - User authentication (register/login/JWT cookies)
  - Dashboard with progress stats, assessment scores, contributions
  - 5-dimension skill assessment with slider interaction
  - Learning progress tracking (start/complete/delete)
  - Document contribution workflow (submit/view/review)
  - SQLite database (aiosqlite)
  - 8 integration tests

- **Phase 6: Automated Governance**
  - GitHub Actions CI/CD: Example Tests job
  - Test summary report (GitHub Step Summary)
  - MkDocs build verification

- **Phase 7: Team Collaboration**
  - TeamManager: Team configuration isolation
    - Create/delete teams, member management
    - Settings isolation, JSON persistence
  - LearningPathManager: Learning path templates
    - 3 preset paths (beginner/practitioner/leader)
    - Role-based filtering, smart recommendations
    - 17 unit tests

- **Phase 8: Ecosystem Integration**
  - VS Code Extension (ai-growth-vscode)
    - Skill assessment, progress tracking, recommendations
    - Webview Dashboard
  - Slack Bot (ai-growth-slack)
    - Command system (!growth assess/progress/recommend/help)
    - User progress tracking, personalized recommendations
    - 7 tests

- **Documentation**
  - Contributor incentive plan (contributor-incentive-plan.md)
  - MkDocs navigation updated for all new docs

### Fixed
- self-correction-loop: Fixed import issues with pytest pythonpath config
- capability-radar, prompt-optimizer: Added pytest configuration

## [1.0.0] - 2026-07-21

### Added
- **Phase 1: Content Foundation**
  - 65+ initial documents across mindset/tools/efficiency layers
  - MkDocs site with full navigation
  - Case studies (11 real-world examples)

- **Phase 2: Quality & Governance**
  - Governance framework (GOVERNANCE.md)
  - Code quality: ruff, mypy, pytest
  - Link audit, case study validation
  - Security scanning (bandit, pip-audit)

- **Phase 3: Knowledge Enhancement**
  - 203 Python files across 10 example projects
  - 175+ root tests passing
  - BM25 search with synonyms
  - Collaborative filtering recommendations

- **Phase 4: AI Enhancement**
  - Vector search (sentence-transformers + cosine similarity)
  - Hybrid search (BM25 + vector RRF fusion)
  - Chat interface (CLI Q&A system)
  - Personalized mentor (5-dimension assessment + L0-L4 levels)
  - 56 ai-navigation tests

### Changed
- README files for all 7 example projects
- CONTEXT.md with full project state
- ROADMAP.md with Phase 1-4 completion

## Stats

| Metric | Count |
|--------|-------|
| Documentation files | 216 |
| Python files | 203 |
| Root tests | 175 |
| Example projects | 10 |
| Commits | 21 |
| GitHub Pages | Live |
