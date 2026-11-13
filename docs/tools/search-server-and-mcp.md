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
→ {"status":"ok","index_ready":true,"document_count":268,"index_built_at":"...","index_build_ms":1524.89}
```

**热重载**（docs 内容变更后免重启重建索引）

```
POST /api/reload
→ {"status":"reloaded","old_document_count":268,"document_count":268,"build_ms":1524.89}
```

**搜索**（中文查询务必 URL 编码，curl 用 `--get --data-urlencode`）

```
GET /api/search?q=质量门禁&limit=3
→ {"query":"质量门禁","total":3,"results":[{"id":...,"title":...,"snippet":...,"score":...,"url":...}],"time_ms":11.69}
```

### 安全与资源约束

- 默认仅绑定 `127.0.0.1`；需局域网访问时设 `SEARCH_HOST` 环境变量并自行加鉴权（当前无内置鉴权/限流）
- systemd 单元已配 `MemoryMax=512M`、`CPUQuota=50%`、`ProtectSystem=strict` 等约束
- 慢请求（>500ms）会打告警日志，响应带 `X-Process-Time-Ms` 头

### 排障

| 现象 | 根因与处置 |
|------|-----------|
| 中文长查询全部零召回 | 环境缺 jieba，分词回退为整串匹配。`uv pip install -p .venv jieba` 后重启服务 |
| 召回质量疑似退化 | 跑 `pytest tests/test_search_recall.py -q`（14 条基准断言）定位是否分词/评分变更引入回归 |
| `ModuleNotFoundError: fastapi` | venv 未装依赖，见部署第 1 步 |
| curl 返回 502 | 本机代理劫持了 127.0.0.1，加 `--noproxy '*'` 或设置 `no_proxy` |
| systemd 启动即失败 | 检查 ExecStart 解释器路径是否存在；`journalctl --user -u search-server.service` 看日志 |

---

## 二、ai_native_mcp_server：MCP 工具服务

### 功能工具

通过 `tools/list` 发现，当前注册：

1. **query_semantic_graph** — 查询语义代码图符号及依赖（参数：`symbol`）
2. **run_architecture_guard** — 架构漂移守卫分层检查（无参数）
3. **knowledge_search** — 全文检索 docs/ 知识库（参数：`query` 必填，`limit` 可选默认 5 上限 20），进程内 TF-IDF 引擎无需 HTTP 服务

### 协议（JSON-RPC 2.0）

```bash
printf '%s\n%s\n%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' \
  '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' \
  '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"run_architecture_guard","arguments":{}}}' \
  | python -m tools.scripts.ai_native_mcp_server
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

- systemd 服务单元：`deploy/systemd/search-server.service`
- TF-IDF/BM25 引擎：`tools/scripts/search/tfidf_engine.py`
- [[efficiency/ai-sdlc|AI 开发全生命周期标准]]

---

## 四、embedding 引入评估结论（2026-08）

用 4 条同义改写查询实测当前 BM25+TF-IDF 引擎：整体可用但存在语义误配
（如"服务器挂了怎么办"命中《无服务器架构》，属字面匹配陷阱）。

**结论：暂不引入 embedding**。理由：

1. 关键词型查询（主流场景）召回已达标，14 条基准全过；
2. 同义改写缺口真实但低频，可通过补充同义词典低成本缓解；
3. embedding 引入成本高（模型依赖、索引重建管道、推理延迟）。

**触发重评条件**（满足其一再评估）：
- 知识库规模超千篇，关键词检索首屏命中率明显下降；
- 真实使用中同义改写类查询占比显著上升；
- `tests/test_search_recall.py` 基准集需加入语义改写断言才能守住质量。
