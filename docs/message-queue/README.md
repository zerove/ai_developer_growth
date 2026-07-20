# 消息队列

> 微服务架构中解耦、削峰、异步处理的核心基础设施。

---

## 核心问题

服务间直接调用导致紧耦合，流量峰值拖垮数据库，耗时操作阻塞用户请求。

**解法**: 引入消息队列，让生产者和消费者各跑各的。

---

## 选型速查

| 维度 | Apache Kafka | RabbitMQ |
|------|-------------|----------|
| 定位 | 分布式事件流平台 | 传统消息代理 |
| 吞吐量 | 百万级/秒 | 万级/秒 |
| 消息顺序 | 分区内严格有序 | 队列内有序 |
| 消息回溯 | ✅ 支持（按 offset 重放） | ❌ 消费即删 |
| 适合场景 | 日志采集、事件溯源、流处理 | 任务队列、RPC、复杂路由 |

**经验法则**: 需要事件回溯和高吞吐选 Kafka，需要灵活路由和低延迟选 RabbitMQ。

---

## 文档索引

- [[docs/message-queue/kafka|Apache Kafka]] — 部署、生产者/消费者模式、Topic 设计、精确一次语义、Schema Registry
- [[docs/message-queue/rabbitmq|RabbitMQ]] — 交换器、队列、路由模式、死信队列、集群

---

## 相关文档

- [[docs/devops/kubernetes|Kubernetes]] — 消息队列的容器化部署
- [[docs/database/nosql|NoSQL]] — 消息持久化存储选型
- [[docs/monitoring/prometheus-grafana|Prometheus + Grafana]] — 消息队列监控
- [[docs/caching/redis|Redis]] — Redis Streams 作为轻量级消息队列替代

---

*本节覆盖主流消息队列的工程实践。最后更新: 2026-07-20*
