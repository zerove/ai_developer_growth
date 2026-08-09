# AI Growth - VS Code Extension

VS Code extension for AI Developer Growth knowledge base integration.

## Features

- **Skill Assessment**: Rate your 5-dimension AI skills directly in VS Code
- **Learning Progress**: Track document reading progress
- **Recommendations**: Get personalized learning path suggestions
- **Dashboard Webview**: Visual progress tracking in sidebar

## Commands

| Command | Description |
|---------|-------------|
| `AI Growth: Skill Assessment` | Interactive 5-dimension skill rating |
| `AI Growth: View Progress` | Show completed documents |
| `AI Growth: Get Recommendations` | Personalized doc suggestions |

## Development

```bash
npm install
npm run compile
# Press F5 to launch Extension Development Host
```

## Install from VSIX

```bash
npm install -g @vscode/vsce
vsce package
code --install-extension ai-growth-*.vsix
```
