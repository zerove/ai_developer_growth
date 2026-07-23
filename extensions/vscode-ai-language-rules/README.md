# AI Language Rules - VS Code Extension

Multi-language code quality validation with 262+ YAML-defined rules.

## Features

- **26 languages** supported (Python, TypeScript, Rust, Go, Java, etc.)
- **5 frameworks** (React, Vue, Django, FastAPI, Spring)
- **262+ rules** covering anti-patterns, naming, complexity, security
- **Auto-fix suggestions** with quick fixes
- **Real-time diagnostics** on file open/save
- **Health score** for project quality overview
- **Custom rules** via `.ai-rules/*.yml`

## Supported Languages

| Language | Extension | Rules |
|----------|-----------|-------|
| Python | `.py` | 21 |
| TypeScript | `.ts`, `.tsx` | 17 |
| Java | `.java` | 17 |
| Go | `.go` | 16 |
| Rust | `.rs` | 15 |
| JavaScript | `.js`, `.jsx` | 8 |
| C++ | `.cpp`, `.h`, `.hpp` | 8 |
| C# | `.cs` | 8 |
| + 18 more... | | |

## Configuration

```json
{
  "aiLanguageRules.enabled": true,
  "aiLanguageRules.maxErrors": 0,
  "aiLanguageRules.maxWarnings": -1,
  "aiLanguageRules.customRulesPath": ".ai-rules",
  "aiLanguageRules.autoFixEnabled": true
}
```

## Commands

- `AI Language Rules: Validate Current File` - Validate the active file
- `AI Language Rules: Validate Entire Project` - Validate all supported files
- `AI Language Rules: Show Health Score` - Display project health score

## Custom Rules

Create `.ai-rules/custom.yml` in your project root:

```yaml
anti_patterns:
  - id: custom-no-debug
    severity: error
    category: code_quality
    pattern: debugger
    message: Remove debugger statements
    fix_hint: Remove the debugger keyword
```

## Requirements

- Python 3.10+ installed
- The `ai_developer_growth` project cloned

## Installation

1. Clone this repository
2. Open in VS Code
3. Press F5 to launch Extension Development Host
4. Or package with `vsce package` and install the `.vsix`
