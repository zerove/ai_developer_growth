# Technical Design: AI-Context-Sync

## 1. 系统架构
AI-Context-Sync 采用**事件驱动**的轻量级架构，确保不干扰开发者的核心编码流程。

### 1.1 逻辑流程图
`Git Commit` $\rightarrow$ `Post-Commit Hook` $\rightarrow$ `Change Analyzer` $\rightarrow$ `LLM Synthesizer` $\rightarrow$ `Doc Updater` $\rightarrow$ `Git Auto-Commit (Optional)`

### 1.2 核心组件
- **Watcher (监听模块)**：
    - 实现方式：基于 `.git/hooks/post-commit` 的 Shell 脚本，调用 Python 主程序。
    - 功能：捕获最后一次 commit 的 `git diff` 和 commit message。
- **Analyzer (分析模块)**：
    - 功能：过滤无关文件（如 `package-lock.json`, `.gitignore`），提取关键代码变更片段。
    - 策略：将变更文件分组，并为每个文件生成简短的语义摘要。
- **Synthesizer (合成模块)**：
    - 核心 Prompt：将 `diff` $\rightarrow$ `commit message` $\rightarrow$ `旧版 CONTEXT.md` $\rightarrow$ `新版 CONTEXT.md`。
    - 逻辑：要求 LLM 仅更新变更部分，保留原有的结构和术语表。
- **Updater (更新模块)**：
    - 功能：使用原子写入更新 `.md` 文件。
    - ADR 触发逻辑：若 commit message 包含 `#ADR`，则启动交互式引导流程生成新 ADR。

## 2. 数据模型与接口
### 2.1 `.ai-sync.json` (配置文件)
```json
{
  "llm": {
    "provider": "openai",
    "model": "gpt-4o",
    "api_key_env": "AI_SYNC_KEY"
  },
  "settings": {
    "ignore": ["*.log", "dist/*", "node_modules/*"],
    "auto_commit": false,
    "context_file": "CONTEXT.md",
    "adr_dir": "docs/adr/"
  }
}
```

### 2.2 LLM 提示词方案 (Prompt Strategy)
- **Context Update Prompt**: "你是一个经验丰富的项目记录员。请分析以下 git diff 和 commit message，更新 `CONTEXT.md` 的【当前进度】部分。要求：保持简洁，使用项目既有术语，只反映本次变更带来的状态升级。"

## 3. 关键挑战与对策
- **上下文爆炸**：如果 diff 过大，将超过 LLM 窗口。
    - *对策*：采用分片摘要法 $\rightarrow$ 先对每个文件做摘要 $\rightarrow$ 再汇总摘要更新文档。
- **文档冗余**：AI 可能会在更新时重复描述相同的功能。
    - *对策*：在 Prompt 中明确要求“对比旧版本，仅记录增量变更”。
- **死循环提交**：自动更新 `CONTEXT.md` 产生的新 commit 又触发 Hook。
    - *对策*：在 commit message 中加入 `[ai-sync]` 标记，Hook 监测到此标记则跳过。

## 4. MVP 实现计划
1. **Phase 1**: 实现 Git Hook $\rightarrow$ 提取 Diff $\rightarrow$ 打印到终端。
2. **Phase 2**: 集成 LLM $\rightarrow$ 根据 Diff 更新 `CONTEXT.md`。
3. **Phase 3**: 实现 `#ADR` 触发逻辑 $\rightarrow$ 生成 ADR 文档。
4. **Phase 4**: 完善配置化管理与过滤机制。
