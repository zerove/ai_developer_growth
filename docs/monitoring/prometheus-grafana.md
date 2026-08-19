---
title: Prometheus + Grafana
description: > 云原生监控的事实标准。指标采集、存储、告警、可视化一套搞定。
category: 工具层
tags: ['Kubernetes', 'Python', '测试', 'SQL', '安全']
difficulty: 基础
reading_time: 10 分钟
updated: 2026-07-21
---

# Prometheus + Grafana

> 云原生监控的事实标准。指标采集、存储、告警、可视化一套搞定。

---

## 1. 核心问题

服务出了问题没有数据支撑，靠猜。需要一个系统自动收集指标、触发告警、生成仪表盘。

Prometheus 负责抓取和存储时间序列数据，Grafana 负责可视化。两者配合覆盖 90% 的监控需求。

---

## 2. 指标类型

```python
from prometheus_client import Counter, Histogram, Gauge

# Counter: 只增不减（请求总数、错误总数）
http_requests_total = Counter("http_requests_total", "HTTP 请求总数", ["method", "path", "status"])

# Histogram: 分布统计（延迟分布）
http_duration_seconds = Histogram("http_duration_seconds", "请求延迟", ["method", "path"])

# Gauge: 可增可减（当前连接数、队列长度）
active_connections = Gauge("active_connections", "当前活跃连接数")
```

四个黄金信号对应的指标：
- 延迟: Histogram 类型，如 `http_duration_seconds`
- 流量: Counter 类型，如 `http_requests_total`
- 错误率: Counter + 标签过滤，`status` 标签筛 5xx
- 饱和度: Gauge 类型，如 CPU、内存、队列长度

---

## 3. 告警规则

```yaml
# alerts.yml
groups:
  - name: app_alerts
    rules:
      # 错误率 > 5% 持续 5 分钟
      - alert: HighErrorRate
        expr: |
          sum(rate(http_requests_total{status=~"5.."}[5m]))
          /
          sum(rate(http_requests_total[5m]))
          > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "错误率超过 5%"
          description: "当前错误率 {{ $value | humanizePercentage }}"

      # P99 延迟 > 1 秒
      - alert: HighLatency
        expr: |
          histogram_quantile(0.99, sum(rate(http_duration_seconds_bucket[5m])) by (le)) > 1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "P99 延迟超过 1 秒"

      # 服务实例数不足
      - alert: TooFewInstances
        expr: count(up{job="myapp"} == 1) < 3
        for: 2m
        labels:
          severity: warning
```

告警规则设计要点：
- `for` 子句防抖动，避免瞬时毛刺触发告警
- `severity` 分级：critical 需要立刻处理，warning 可以排队
- 描述字段用模板变量，告警时能直接看到具体值

---

## 4. Grafana 仪表盘

```json
{
  "panels": [
    {
      "title": "请求速率",
      "type": "stat",
      "targets": [{
        "expr": "sum(rate(http_requests_total[5m]))",
        "legendFormat": "{{method}} {{path}}"
      }]
    },
    {
      "title": "延迟分布",
      "type": "timeseries",
      "targets": [
        {"expr": "histogram_quantile(0.50, sum(rate(http_duration_seconds_bucket[5m])) by (le))", "legendFormat": "P50"},
        {"expr": "histogram_quantile(0.95, sum(rate(http_duration_seconds_bucket[5m])) by (le))", "legendFormat": "P95"},
        {"expr": "histogram_quantile(0.99, sum(rate(http_duration_seconds_bucket[5m])) by (le))", "legendFormat": "P99"}
      ]
    }
  ]
}
```

仪表盘组织原则：
- 一层 Overview（关键指标一览），下钻到 Service 级别
- 每个仪表盘不超过 20 个面板
- 面板标题要能自解释，看一眼就知道是什么

---

## 5. Exporter 集成

```yaml
# 常用 Exporter
# Node Exporter — 系统指标（CPU、内存、磁盘）
# Redis Exporter — Redis 指标
# PostgreSQL Exporter — 数据库指标
# Kafka Exporter — 消息队列指标

# docker-compose 示例
services:
  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    ports:
      - "9090:9090"

  node-exporter:
    image: prom/node-exporter:latest
    command: --path.rootfs=/host
    volumes:
      - /:/host:ro

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD}
```

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'myapp'
    metrics_path: '/metrics'
    static_configs:
      - targets: ['app:8080']

  - job_name: 'redis'
    static_configs:
      - targets: ['redis-exporter:9121']
```

---

## 6. 常见陷阱

| 陷阱 | 症状 | 解法 |
|------|------|------|
| 告警风暴 | 一次事故几十条告警 | 抑制规则、分组 |
| 指标爆炸 | 高基数标签导致 OOM | 限制 label 值域 |
| 采样间隔太长 | 毛刺看不到 | 关键指标 15s，非关键 60s |
| 仪表盘过多 | 没人看 | 定期清理，只保留有用的 |

---

## 相关文档

- [[docs/monitoring/logging|集中化日志]] — 日志和指标互补
- [[docs/devops/kubernetes|Kubernetes]] — K8s 内置 Prometheus 集成
- [[docs/caching/redis|Redis]] — Redis Exporter 配置
- [[docs/message-queue/kafka|Kafka]] — Kafka Exporter 配置

---

*本规范随 Prometheus/Grafana 生态演进持续更新。最后更新: 2026-07-20*
