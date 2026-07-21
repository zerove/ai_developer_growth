---
title: Apache Kafka
description: > 分布式事件流平台，适合高吞吐、可回溯的场景。
category: 工具层
tags: ['Docker', 'Kubernetes']
difficulty: 初级
reading_time: 10 分钟
updated: 2026-07-21
---

# Apache Kafka

> 分布式事件流平台，适合高吞吐、可回溯的场景。

---

## 1. 核心问题

日志采集丢数据、微服务间事件溯源困难、流式处理缺乏可靠的基础设施。

Kafka 通过持久化 commit log 解决这些问题：消息写入磁盘、按 offset 可重放、分区并行处理。

---

## 2. Topic 设计

```bash
# ✅ 按业务域划分，而非按数据类型
# orders          — 订单事件
# user-actions    — 用户行为
# payments        — 支付流水

# ❌ 避免：一个 topic 塞所有事件
# events          — 混乱，无法独立消费
```

分区数决定并行度。经验值：分区数 = 消费者实例数 × 2。分区过多增加 leader 选举开销。

```bash
# 创建 topic
kafka-topics.sh --create \
  --bootstrap-server localhost:9092 \
  --topic orders \
  --partitions 6 \
  --replication-factor 3
```

---

## 3. 生产者配置

```properties
# 精确一次语义（必须同时配置两端）
acks=all
enable.idempotence=true
retries=2147483647
max.in.flight.requests.per.connection=5  # 幂等下可设为 5

# 批量发送：吞吐量换延迟
batch.size=16384
linger.ms=5
compression.type=lz4
```

关键点：`acks=all` + `enable.idempotence=true` 是精确一次的最低要求。生产者端幂等保证单分区不重复，跨分区需要事务。

---

## 4. 消费者模式

```java
// ✅ 消费者组：水平扩展
Properties props = new Properties();
props.put("group.id", "order-processor");
props.put("enable.auto.commit", "false");  // 手动提交，防止重复消费
props.put("isolation.level", "read_committed");  // 只读已提交消息

consumer.subscribe(Arrays.asList("orders"));

while (true) {
    ConsumerRecords<String, String> records = consumer.poll(Duration.ofMillis(100));
    for (ConsumerRecord<String, String> record : records) {
        processOrder(record.value());
    }
    consumer.commitSync();  // 处理完再提交
}
```

`enable.auto.commit=false` + `commitSync()` 是最安全的组合。自动提交会导致消息丢失。

---

## 5. Schema Registry

```bash
# 注册 Schema（Avro）
curl -X POST -H "Content-Type: application/vnd.schemaregistry.v1+json" \
  --data '{"schema": "{\"type\":\"record\",\"name\":\"Order\",\"fields\":[{\"name\":\"id\",\"type\":\"string\"},{\"name\":\"amount\",\"type\":\"double\"}]}"}' \
  http://localhost:8081/subjects/orders-value/versions
```

Schema Registry 保证生产者和消费者的数据格式兼容。推荐在 CI 中加入 schema 兼容性检查：

```bash
# 兼容性检查
curl -X POST -H "Content-Type: application/json" \
  --data '{"schema": "..."}' \
  http://localhost:8081/subjects/orders-value/compatibility
```

---

## 6. 部署与监控

```yaml
# docker-compose 核心配置
services:
  kafka:
    image: confluentinc/cp-kafka:7.6.0
    environment:
      KAFKA_BROKER_ID: 1
      KAFKA_NUM_PARTITIONS: 6
      KAFKA_DEFAULT_REPLICATION_FACTOR: 3
      KAFKA_LOG_RETENTION_HOURS: 168  # 7 天
      KAFKA_LOG_SEGMENT_BYTES: 1073741824
    ports:
      - "9092:9092"
```

关键监控指标：
- `UnderReplicatedPartitions` > 0 表示有副本落后
- `Consumer Lag` 持续增长说明消费者跟不上
- `Request latency` 升高检查磁盘 IO

---

## 相关文档

- [[docs/message-queue/rabbitmq|RabbitMQ]] — 轻量级替代方案
- [[docs/caching/redis|Redis]] — Redis Streams 场景
- [[docs/devops/kubernetes|Kubernetes]] — Kafka 的 K8s 部署（Strimzi Operator）
- [[docs/monitoring/prometheus-grafana|Prometheus + Grafana]] — Kafka 指标采集

---

*本规范随 Kafka 生态演进持续更新。最后更新: 2026-07-20*
