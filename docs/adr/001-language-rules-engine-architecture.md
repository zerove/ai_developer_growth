# ADR-001: Language Rules Engine Architecture

## Status

Accepted

## Date

2026-07-23

## Context

We need a multi-language code quality validation system that:
- Supports 26+ languages with YAML-defined rules
- Provides real-time IDE feedback via LSP
- Integrates with CI/CD pipelines
- Allows custom rules per project
- Generates multiple report formats

## Decision

We will use a **monolithic engine with modular internal structure**:

```
tools/scripts/
  _common.py              # Shared utilities (paths, hashing, YAML)
  validate_language_rules.py  # Core engine (2160 lines)
  detect_language.py      # Language detection from file extensions
  ai_quality_gate.py      # jcode pipeline integration
  # Domain-specific tools:
  rule_marketplace.py     # Rule pack management
  rule_author.py          # Rule creation CLI
  rule_tracker.py         # Effectiveness tracking
  rule_registry.py        # Central registry
  generate_fixes.py       # AI-assisted fix generation
  validate_rule_tests.py  # Regex test framework
  git_diff_incremental.py # Git diff integration
  rule_visualize.py       # Web UI
  rule_editor.py          # Live editor
```

### Key Design Choices

1. **YAML as rule format**: Human-readable, diffable, toolable
2. **Regex-based pattern matching**: Simple, fast, cross-language
3. **Python-only engine**: No external runtime dependencies (only pyyaml)
4. **Subprocess for IDE integration**: LSP server calls validate_language_rules.py
5. **File-based caching**: MD5 hashing for incremental validation

## Consequences

### Positive
- Single language (Python) for all tooling
- Easy to add new languages (just add YAML)
- No compilation step needed
- Works offline

### Negative
- 2160-line main file is hard to navigate
- Regex-only rules miss some patterns (e.g., control flow)
- No type-aware analysis for most languages (except Python AST)

## Alternatives Considered

1. **Tree-sitter based**: More powerful but requires native dependencies
2. **LSP-native**: Would require per-language LSP servers
3. **Plugin architecture**: More flexible but more complex

## Follow-up

- Refactor validate_language_rules.py into modules (ADR-002)
- Add tree-sitter for Python/TypeScript deep analysis (future)
