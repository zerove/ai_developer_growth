# Extensions Overview

本项目包含 4 个 IDE/编辑器扩展，集成 ADG 治理规则引擎。

| 扩展 | 平台 | 技术栈 | 后端 |
|------|------|--------|------|
| ADG Governance | VS Code | `vscode-adg/` (JS) | `adg check --json` CLI |
| ADG Governance | Zed | `zed-adg/` (Rust) | `adg check --json` CLI |
| AI Language Rules | VS Code | `vscode-ai-language-rules/` (JS) | `adg check --json` CLI |
| AI Language Rules | Zed | `ai-language-rules/` (Python LSP) | `adg check --json` CLI |

## 架构

所有扩展统一通过 `adg` CLI 获取诊断数据，不再直接调用旧的 YAML 规则解析器：

```
用户编辑器 → extension/adapter → adg CLI → rules_engine → YAML 规则文件
                          ↓
                   Problems/Diagnostics 面板
```

优点：
- **统一数据源**：所有扩展调同一条 `adg check --json` 命令，结果一致
- **零重复**：规则逻辑在引擎端，扩展只需解析 JSON 并渲染
- **自动获得更新**：新增语言/规则/修复能力后扩展无需修改
- **自动修复**：`adg fix --json` 统一入口，支持 4 语言 29+ 修复类型

## 扩展详情

| 目录 | 入口文件 | 核心能力 |
|------|----------|----------|
| `vscode-adg/` | `extension.js` (main) | 保存时扫描、Quick Fix、状态栏、Project Check、Git Hooks |
| `vscode-ai-language-rules/` | `extension.js` | 打开/保存时扫描、Auto-fix 命令、高度灵活配置 |
| `ai-language-rules/` | `lsp_server.py` | LSP 协议、stdio/TCP 双模式、Zed/Sublime 兼容 |
| `zed-adg/` | `src/lib.rs` | Rust 原生与 `adg` CLI 集成，类型安全解析 |

---

*所有扩展于 2026-07-30 同步至 v2.3+。*
