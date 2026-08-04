# ADG VS Code Extension

实时代码质量扫描，保存文件时自动检测反模式和安全问题。

## 安装

```bash
# 确保已安装 adg CLI
pip install ai-dev-framework

# 从源码安装
cd extensions/vscode-adg
code --install-extension .
```

或者将 `extensions/vscode-adg` 目录复制到 `.vscode/extensions/`。

## 功能

- **保存时自动扫描**：文件保存时运行 `adg scan`
- **Problems 面板集成**：问题直接显示在 VS Code Problems 面板
- **命令面板支持**：`ADG: Scan Current File` / `ADG: Scan Workspace`
- **严重性过滤**：可配置仅显示 error/warning 级别

## 配置

| 设置 | 默认值 | 说明 |
|------|--------|------|
| `adg.scanOnSave` | `true` | 保存时自动扫描 |
| `adg.severityThreshold` | `"warning"` | 问题显示阈值 |

## 系统要求

- VS Code 1.85+
- Python 3.10+
- `adg` CLI (`pip install ai-dev-framework`)
