---
title: 知识检索服务与 AI-Native MCP 服务器使用指南
description: search-server HTTP API 与 ai_native_mcp_server JSON-RPC 2.0 工具的部署、调用与排障
category: 工具层
tags:
    - search
    - mcp
    - deployment
    - fastapi
    - jsonrpc
difficulty: 基础
---

# 知识检索服务与 AI-Native MCP 服务器使用指南

本项目提供两个服务化入口，把 267 篇知识库与架构治理能力暴露给外部调用方：

| 服务 | 入口脚本 | 协议 | 典型调用方 |
|------|----------|------|-----------|
| 知识检索 API | `scripts/search-server.py` | HTTP (FastAPI) | 浏览器、脚本、CI |
| AI-Native SDLC | `tools/scripts/ai_native_mcp_server.py` | stdin/stdout JSON-RPC 2.0 | Claude、Cursor 等 MCP 客户端 |

---

## 一、search-server：知识检索 HTTP 服务

### 功能

- 全量索引 `docs/` 下 267 篇文档（title/content/tags/category/difficulty）
- BM25 评分 + 同义词扩展 + 中文 jieba 分词
- 健康检查端点供 systemd/负载均衡探活

### 部署（推荐 systemd 用户服务）

```bash
# 1. 安装依赖到项目 venv（uv 管理）
uv pip install -p .venv -r requirements.txt

# 2. 安装并启动用户级服务
cp deploy/systemd/search-server.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now search-server.service

# 3. 验证
systemctl --user is-active search-server.service
curl --noproxy '*' http://127.0.0.1:8001/api/health
# {"status":"ok","index_ready":true,"document_count":267}
```

### API

**健康检查**

```
GET /api/health
→ {"status":"ok","index_ready":true,"document_count":267}
```

**搜索**（中文查询务必 URL 编码，curl 用 `--get --data-urlencode`）

```
GET /api/search?q=质量门禁&limit=3
→ {"query":"质量门禁","total":3,"results":[{"id":...,"title":...,"snippet":...,"score":...,"url":...}],"time_ms":11.69}
```

### 排障

| 现象 | 根因与处置 |
|------|-----------|
| 中文长查询全部零召回 | 环境缺 jieba，分词回退为整串正则匹配。`uv pip install -p .venv jieba` 后重启服务 |
| `ModuleNotFoundError: fastapi` | venv 未装依赖，见部署第 1 步 |
| curl 返回 502 | 本机代理劫持了 127.0.0.1，加 `--noproxy '*'` 或设置 `no_proxy` |
| systemd 启动即失败 | 检查 ExecStart 解释器路径是否存在；`journalctl --user -u search-server.service` 看日志 |

---

## 二、ai_native_mcp_server：MCP 工具服务

### 功能工具

通过 `tools/list` 发现，当前注册：

1. **query_semantic_graph** — 查询语义代码图符号及依赖（参数：`symbol`）
2. **run_architecture_guard** — 架构漂移守卫分层检查（无参数）

### 协议（JSON-RPC 2.0）

```bash
printf '%s\n%s\n%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' \
  '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' \
  '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"run_architecture_guard","arguments":{}}}' \
  | python tools/scripts/ai_native_mcp_server.py
```

支持方法：

| 方法 | 说明 |
|------|------|
| `initialize` | 握手，返回 protocolVersion 与 serverInfo |
| `tools/list` | 列出全部注册工具及参数元数据 |
| `tools/call` | 调用工具，结果包装为 `content` 数组 + `isError` |
| `ping` | 心跳，返回空 result |

错误响应遵循 JSON-RPC 规范（如未知方法返回 `-32601 Method not found`）。
旧版裸 `{tool, arguments}` 字段协议保留兼容，但新集成一律使用标准协议。

### MCP 客户端接入

在支持 stdio 传输的 MCP 客户端配置中添加：

```json
{
  "command": "python",
  "args": ["tools/scripts/ai_native_mcp_server.py"],
  "cwd": "<项目根目录绝对路径>"
}
```

---

## 三、测试

```bash
python -m pytest tests/test_search_server_smoke.py tests/test_ai_native_mcp_server.py -q
```

覆盖：索引构建、中英文查询、健康检查、JSON-RPC 三步握手、旧协议回归。

---

## 相关文档

- [[deploy/systemd/search-server.service|systemd 服务单元]]
- [[tools/scripts/tfidf_engine|TF-IDF/BM25 引擎]]
- [[efficiency/ai-sdlc|AI 开发全生命周期标准]]
