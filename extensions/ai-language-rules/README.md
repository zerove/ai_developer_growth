# AI Language Rules - Zed Extension

Real-time code quality diagnostics for 26+ programming languages in Zed editor.

## Features

- **26 languages**: Python, TypeScript, Rust, Go, Java, Kotlin, C#, JavaScript, C++, Swift, Scala, Elixir, Lua, Ruby, PHP, Zig, R, Clojure, Haskell, Dart, PowerShell, Perl, Assembly, Fortran, MATLAB, GraphQL
- **5 frameworks**: React, Vue, Django, FastAPI, Spring
- **Real-time diagnostics**: Anti-patterns, naming conventions, thresholds
- **Auto-fix suggestions**: Fix hints displayed inline
- **Custom rules**: Override severity or add project-specific rules via `.ai-rules/`
- **Cross-language security**: Universal security rules applied to all files

## Installation

### Option 1: Local Development
```bash
# Clone and link to Zed extensions directory
cd extensions/ai-language-rules
ln -s "$(pwd)" ~/.zed/extensions/ai-language-rules
```

### Option 2: Manual Setup
1. Copy `extension.toml` to `~/.zed/extensions/ai-language-rules/`
2. Copy `lsp_server.py` to the same directory
3. Install dependencies: `pip install pyyaml`
4. Restart Zed

## Configuration

Add to your Zed `settings.json`:

```json
{
  "lsp": {
    "ai-language-rules": {
      "binary": {
        "path": "python3",
        "arguments": ["~/.zed/extensions/ai-language-rules/lsp_server.py", "--stdio"]
      }
    }
  }
}
```

### Project-specific overrides

Create `.ai-rules/` in your project root:

```yaml
# .ai-rules/custom.yml
anti_patterns:
  - id: my-no-todo
    name: No TODOs allowed
    severity: error
    category: code_quality
    pattern: 'TODO|FIXME'
    message: TODOs are not allowed in this project
```

## How it works

1. The extension starts an LSP server that reads YAML rules
2. When you open or save a file, the server validates it against language rules
3. Diagnostics appear as errors/warnings/info in the editor
4. Hover over issues to see fix hints

## Rule sources

- Built-in rules: `ai-dev-framework/languages/*/rules.d/anti_patterns.yml`
- Framework rules: `ai-dev-framework/frameworks/*/rules.d/anti_patterns.yml`
- Common rules: `ai-dev-framework/common/security.yml`
- Custom rules: `<project>/.ai-rules/*.yml`
