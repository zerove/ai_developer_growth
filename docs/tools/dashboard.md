---
title: "ADG Quality Dashboard"
description: "ADG 质量仪表板：可视化代码质量报告、趋势与门禁状态"
category: 工具层
tags: ['可视化代码质量报告的', '仪表板', '启动', '安装依赖', '启动仪表板', '访问']
difficulty: 基础
---

# ADG Quality Dashboard

> 可视化代码质量报告的 Web 仪表板。

## 启动

```bash
# 安装依赖
pip install fastapi uvicorn

# 启动仪表板
adg dashboard --port 8765
```

访问 http://localhost:8765

## 功能

- **质量趋势图**: 跟踪 errors/warnings 随时间的变化
- **文件级详情**: 每个文件的通过/失败状态
- **规则违规分析**: 按类别分组的违规统计
- **历史对比**: 比较不同时间点的质量数据

## API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/` | GET | Web 仪表板页面 |
| `/api/trend` | GET | 质量趋势数据 (支持 `?limit=N`) |
| `/api/latest` | GET | 最新完整报告 |
| `/api/record` | POST | 记录新的质量运行结果 |

## CI/CD 集成

在 CI 流水线中自动记录质量数据：

```yaml
# GitHub Actions
- name: Record quality data
  run: |
    adg check . --json > adg-report.json
    curl -X POST http://your-dashboard:8765/api/record \
      -H "Content-Type: application/json" \
      -d @adg-report.json
```

## 技术栈

- 后端: FastAPI + SQLite
- 前端: Chart.js + 原生 CSS (暗色主题)
- 数据库: SQLite (adg_quality.db)
