---
title: "ADG LSP Server - IDE 集成"
description: "ADG 语言服务器协议（LSP）服务：编辑器内实时规则提示与诊断"
category: 工具层
tags: ['集成', '通过', '提反馈', '安装', '启动', '直接启动']
difficulty: 基础
---

# ADG LSP Server - IDE 集成

> 通过 Language Server Protocol 提反馈。

## 安装

```bash
pip install pygls
```

## 启动

```bash
# 直接启动
python -m tools.scripts.rules_engine.lsp_server

# 或通过 CLI
adg lsp
```

## VS Code 配` 中添加：

```json
{
  "languageServerExample.path": "python",
  "languageServerExample.args": ["-m", "tools.scripts.rules_engine.lsp_server"],
  "languageServerExample.command": "python"
}
```

然后在 `extensions.json` 中注册：

```json
{
  "recommendations": []
}
```

## Neovim 配置

使用 `nvim-lspconfig`：

```lua
local lspconfig = require('lspconfig')

lspconfig.adg_governance = {
  cmd = { 'python', '-m', 'tools.scripts.rules_engine.lsp_server' },
  filetypes = { 'python', 'javascript', 'typescript', 'rust', 'java' },
  root_dir = lspconfig.util.root_pattern('.adg', '.git'),
}
```

## 功能

### Diagnostics (诊断)

- 🔴 Error: 必须修复的问题
- 🟡 Warning: 应该修复的问题
- 🔵 Info: 建议改进的地方

### Hover (悬停)

将鼠标悬停在问题代码上，显示：
- 规则 ID
- 严重度
- 问题描述
- 修复建议

### Code Actions (代码操作)

点击灯泡图标，获取快速修复建议。

## 支持的语言

- Python
- JavaScript / TypeScript
- Rust
- Java
- Go
- Kotlin
- Swift
