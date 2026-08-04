# 发布说明 v2.3.0

**日期**: 2026-07-30

## 亮点

### 🏗️ CLI 重构：消除双 FIX_RULES
将 1321 行独立脚本替换为 45 行薄包装，全部逻辑委托到模块化 CLI。单源真相时代正式到来。
- 新增 `pyproject.toml` 的 `[project.scripts]` 入口
- 新增 `python -m tools.scripts.adg_cli` 调用方式
- 知识库联动：`adg check --with-docs` 注入 `related_docs` 到规则输出

### 🖥️ Dashboard 2.0 + 跨语言自动修复
- 多项目报告聚合、趋势仪表板
- Auto-fix 引擎覆盖 7 语言（Python/JS/TS/Rust/Java/Go/Ruby）
- CI/CD 集成模板（GitLab/Azure/Jenkins/CircleCI/GitHub Actions）

### 🔌 4 个编辑器扩展同步
全部统一调用 `adg check --json`：
- **VS Code ADG**: 9 命令 + 状态栏 + Quick Fix
- **VS Code AI Language Rules**: v2.0 + auto-fix
- **LSP Server**: `adg` 后端替代旧 YAML 解析
- **Zed ADG**: Rust 库 + CLI 运行器

### 🌐 P2 生态系统
- 社区 PR 案例校验 CI 工作流
- 规则→文档映射引擎（421 条规则映射）
- `adg check --with-docs` 输出关联文档

## 统计

| 指标 | 数值 |
|------|------|
| 变更文件 | 14+ |
| 代码行数 | +1193/−516 |
| 规则→文档映射 | 421 条 |
| 支持编辑器 | 4（VS Code x2, LSP, Zed） |

## 安装

```bash
pip install -e .
# 或从源码
cd ai_developer_growth
pip install -e .
```

## 升级注意

- 如果之前通过 `cp ~/.local/bin/adg` 安装独立脚本，`pip install -e .` 会自动覆盖为 console_scripts 入口
- `adg` 命令接口向后兼容，无破坏性变更
