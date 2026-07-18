# MCP 服务器配置指南

本指南说明如何将 AI-Context-Sync MCP 服务器集成到 opencode 中。

## 1. 安装依赖

```bash
cd examples/ai-context-sync
pip install -r requirements.txt
```

## 2. 配置 opencode

在项目根目录创建或编辑 `opencode.json`：

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "ai-context-sync": {
      "command": "python",
      "args": ["-m", "src.mcp_server"],
      "cwd": "/home/zeron/dev/ai_developer_growth/examples/ai-context-sync",
      "enabled": true
    }
  }
}
```

**或者使用绝对路径：**

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "ai-context-sync": {
      "command": "python3",
      "args": ["/home/zeron/dev/ai_developer_growth/examples/ai-context-sync/src/mcp_server.py"],
      "enabled": true
    }
  }
}
```

## 3. 可用的 MCP 工具

配置完成后，以下工具将自动在 opencode 中可用：

| 工具名称 | 功能描述 | 参数 |
|----------|----------|------|
| `ai_sync` | 同步项目上下文 (CONTEXT.md) | `config`, `dry_run` |
| `ai_guard` | 根据架构决策审计代码 | `config` |
| `ai_audit` | 根据开发规范审计代码 | `config`, `strict` |
| `ai_flow` | 执行完整的 AI-Native 开发流水线 | `task`, `config` |
| `ai_trace` | 跟踪架构决策历史 | `adr_id`, `config` |
| `ai_map` | 生成架构决策图 (Mermaid) | `config` |
| `ai_evolve` | 分析审计历史并提议规范更新 | `config`, `batch` |
| `ai_scaffold` | 从模板初始化项目 | `template`, `target_dir`, `config` |
| `ai_explain` | 使用 ADR 上下文解释决策 | `query`, `config` |

## 4. 可用的 MCP 资源

| 资源 URI | 功能描述 |
|----------|----------|
| `context://{config_path}` | 读取项目 CONTEXT.md 文件 |
| `adr://{adr_id}` | 读取特定的 ADR 文件 |
| `specs://{language}` | 读取语言特定的开发规范 |

## 5. 使用示例

### 在 opencode 中使用

配置完成后，您可以在 opencode 中直接使用这些工具：

```
# 同步项目上下文
请使用 ai_sync 工具同步最新的项目上下文

# 审计代码
请使用 ai_guard 工具检查当前代码是否符合架构决策

# 执行开发任务
请使用 ai_flow 工具实现用户权限管理系统
```

### 手动测试 MCP 服务器

```bash
cd /home/zeron/dev/ai_developer_growth/examples/ai-context-sync
python -m src.mcp_server
```

## 6. 环境变量配置

确保设置以下环境变量：

```bash
# LLM API 密钥（用于 AI 功能）
export AI_SYNC_KEY="your-api-key"

# 或者使用 opencode 配置的 LLM
# AI-Context-Sync 会自动检测 opencode 环境
```

## 7. 故障排除

### MCP 服务器无法启动

1. 检查依赖是否安装：
   ```bash
   pip install mcp fastmcp
   ```

2. 检查 Python 路径：
   ```bash
   cd /home/zeron/dev/ai_developer_growth/examples/ai-context-sync
   python -c "import src.mcp_server; print('OK')"
   ```

### opencode 无法连接 MCP 服务器

1. 检查 opencode.json 配置是否正确
2. 确保 MCP 服务器路径正确
3. 查看 opencode 日志获取错误信息

### 工具调用失败

1. 确保在正确的项目目录中运行
2. 检查 `.ai-sync.json` 配置文件是否存在
3. 确保 Git 仓库已初始化

## 8. 高级配置

### 自定义 MCP 服务器名称

```json
{
  "mcp": {
    "my-custom-name": {
      "command": "python",
      "args": ["-m", "src.mcp_server"],
      "cwd": "/path/to/ai-context-sync"
    }
  }
}
```

### 禁用特定工具

目前 MCP 服务器不支持选择性禁用工具。如需此功能，请提交 Issue。

---

*最后更新：2026-07-17*
