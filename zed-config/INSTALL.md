# Zed AI 工作流配置安装指南

本配置包旨在为开发者提供一个优化后的 Zed 编辑器环境，旨在减少摩擦，最大化“心流”状态，特别针对 AI 辅助开发进行了优化。

## 📦 包含内容

- `settings.json`: 优化后的编辑器设置（字体、主题、AI 面板行为、自动保存等）。
- `snippets.json`: 一组高效的 AI 提示词片段（用于重构、TDD、ADR 等）。

## 🛠️ 安装步骤

### 1. 应用编辑器设置 (`settings.json`)

1. 打开 Zed。
2. 使用快捷键 `Cmd + ,` (macOS) 或 `Ctrl + ,` (Linux/Windows) 打开设置文件。
3. 将 `ai-developer-growth/zed-config/settings.json` 中的内容复制并粘贴到你的 `settings.json` 中。
   - *注意：如果你已有部分设置，请手动合并相关项。*

### 2. 安装 AI 代码片段 (`snippets.json`)

Zed 支持自定义代码片段。为了启用本包中的 AI 提示词：

1. 找到 Zed 的片段配置目录：
   - macOS: `~/.config/zed/snippets/`
   - Linux: `~/.config/zed/snippets/`
2. 如果目录不存在，请创建它。
3. 将 `snippets.json` 放入该目录，或者将其内容合并到你针对特定语言的片段文件中（例如 `rust.json` 或 `typescript.json`）。
4. 在编辑器中输入前缀（如 `ai-refactor`）并按下 `Tab` 键即可快速插入提示词。

## 🚀 使用技巧

- **AI 重构**: 选中一段代码 $\rightarrow$ 输入 `ai-refactor` $\rightarrow$ 发送给 AI 助手。
- **TDD 驱动**: 输入 `ai-tdd` $\rightarrow$ 填写需求 $\rightarrow$ 让 AI 编写失败测试用例。
- **架构记录 (ADR)**: 输入 `ai-adr` $\rightarrow$ 快速生成架构决策草案。
- **自动保存**: 设置中已开启 `on_focus_change`，确保 AI 助手始终能读取到你最新的代码修改。

## 🎨 推荐字体
本配置推荐使用 **JetBrains Mono**。如果尚未安装，建议安装以获得最佳视觉体验。
