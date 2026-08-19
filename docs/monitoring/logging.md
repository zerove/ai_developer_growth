---
title: 集中化日志
description: > 把散落在各台机器上的日志收集到一起，方便搜索、分析、排查问题。
category: 工具层
tags: ['API', 'AI', 'Kubernetes', 'Python', 'SQL']
difficulty: 高级
reading_time: 10 分钟
updated: 2026-07-21
---

# 集中化日志

> 把散落在各台机器上的日志收集到一起，方便搜索、分析、排查问题。

---

## 1. 核心问题

出了 bug 去哪台机器看日志？日志格式不统一，grep 半天找不到关键信息。多实例部署后，日志分散在几十个容器里。

集中化日志把所有节点的日志收集到统一存储，提供搜索和分析能力。

---

## 2. 架构选型

| 方案 | 存储 | 查询 | 适合场景 |
|------|------|------|---------|
| ELK（Elasticsearch + Logstash + Kibana） | Elasticsearch | Kibana UI + Lucene | 需要全文搜索、复杂聚合 |
| Loki + Grafana | 对象存储（S3） | LogQL | 已有 Grafana，资源有限 |
| ClickHouse | ClickHouse | SQL | 日志分析 + 数仓一体 |

资源有限选 Loki（只索引标签，不索引内容），搜索需求强选 ELK。

---

## 3. 结构化日志

```python
import structlog

# ✅ 正确: 结构化日志
logger = structlog.get_logger()
logger.info("order_created", order_id="ORD-2026-001", user_id=1001, amount=299.99, duration_ms=45)

# 输出: {"event": "order_created", "order_id": "ORD-2026-001", "user_id": 1001, "amount": 299.99, "duration_ms": 45, "timestamp": "2026-07-20T10:30:00Z"}

# ❌ 禁止: 非结构化文本日志
logger.info(f"Order {order_id} created by user {user_id} with amount {amount}")
# 难以机器解析，无法聚合分析
```

结构化日志关键点：
- 键值对格式，方便 JSON 解析
- 日志级别要有意义：DEBUG 开发调试，INFO 关键业务事件，WARN 可恢复异常，ERROR 需要干预
- 敏感信息脱敏（手机号、身份证、密码）

---

## 4. ELK Stack

```yaml
# docker-compose: ELK
services:
  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.14.0
    environment:
      - discovery.type=single-node
      - xpack.security.enabled=false
      - "ES_JAVA_OPTS=-Xms512m -Xmx512m"
    volumes:
      - es_data:/usr/share/elasticsearch/data
    ports:
      - "9200:9200"

  logstash:
    image: docker.elastic.co/logstash/logstash:8.14.0
    volumes:
      - ./logstash.conf:/usr/share/logstash/pipeline/logstash.conf
    depends_on:
      - elasticsearch

  kibana:
    image: docker.elastic.co/kibana/kibana:8.14.0
    environment:
      - ELASTICSEARCH_HOSTS=http://elasticsearch:9200
    ports:
      - "5601:5601"
```

```ruby
# logstash.conf — 解析 JSON 日志
input {
  beats { port => 5044 }
}

filter {
  json {
    source => "message"
  }
  date {
    match => ["timestamp", "ISO8601"]
  }
  mutate {
    remove_field => ["timestamp"]
  }
}

output {
  elasticsearch {
    hosts => ["elasticsearch:9200"]
    index => "app-logs-%{+YYYY.MM.dd}"
  }
}
```

---

## 5. Loki（轻量替代）

```yaml
# promtail 配置：采集日志
server:
  http_listen_port: 9080

positions:
  filename: /tmp/positions.yaml

clients:
  - url: http://loki:3100/loki/api/v1/push

scrape_configs:
  - job_name: containers
    docker_sd_configs:
      - host: unix:///var/run/docker.sock
    relabel_configs:
      - source_labels: ['__meta_docker_container_name']
        target_label: 'container'
```

```logql
# Loki 查询语法（LogQL）
# 查找错误日志
{container="app"} |= "ERROR"

# 按容器聚合错误率
rate({container="app"} |= "ERROR" [5m])

# 正则提取字段
{job="app"} | json | line_format "{{.order_id}}: {{.message}}"
```

Loki 的优势：只索引标签不索引内容，存储成本远低于 Elasticsearch。

---

## 6. 日志规范

| 规范 | 说明 |
|------|------|
| 统一格式 | 全项目 JSON 格式，字段命名一致 |
| 必要字段 | timestamp、level、service、message、trace_id |
| 脱敏 | 手机号、邮箱、密码一律脱敏 |
| 轮转 | 单文件不超过 100MB，保留 30 天 |
| 采样 | DEBUG 日志在生产环境采样 1% |

```python
# 完整的日志字段示例
{
    "timestamp": "2026-07-20T10:30:00.123Z",
    "level": "info",
    "service": "order-service",
    "trace_id": "abc123def456",
    "message": "order_created",
    "order_id": "ORD-001",
    "user_id": "u_1001",
}
```

`trace_id` 是串联日志和链路追踪的关键字段。所有服务必须传递和记录。

---

## 相关文档

- [[docs/monitoring/prometheus-grafana|Prometheus + Grafana]] — 指标监控
- [[docs/devops/docker|Docker]] — 容器日志配置
- [[docs/devops/kubernetes|Kubernetes]] — K8s 日志收集（Fluentd / Fluent Bit）
- [[docs/security/authentication|认证授权]] — 日志中的安全审计

---

*本规范随日志生态演进持续更新。最后更新: 2026-07-20*
