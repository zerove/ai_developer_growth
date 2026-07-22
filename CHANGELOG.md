# Changelog

All notable changes to the AI Developer Growth project.

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
