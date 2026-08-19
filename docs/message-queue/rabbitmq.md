---
title: RabbitMQ
description: > 轻量级消息代理，适合灵活路由和复杂消息模式。
category: 工具层
tags: ['Docker', 'Python']
difficulty: 高级
reading_time: 10 分钟
updated: 2026-07-21
---

# RabbitMQ

> 轻量级消息代理，适合灵活路由和复杂消息模式。

---

## 1. 核心问题

微服务间需要可靠的消息传递，但 Kafka 的运维成本过高。需要灵活的消息路由规则，而不仅仅是发布/订阅。

RabbitMQ 基于 AMQP 协议，通过交换器（Exchange）+ 路由键（Routing Key）实现灵活的消息分发。

---

## 2. 交换器类型

| 类型 | 路由规则 | 典型场景 |
|------|---------|---------|
| direct | routing key 精确匹配 | 点对点任务分发 |
| fanout | 广播到所有绑定队列 | 事件通知 |
| topic | 通配符匹配（`*` 一个词，`#` 多个词） | 按业务域路由 |
| headers | 按消息头匹配 | 少用，性能差 |

```python
# ✅ Topic 交换器：按业务域灵活路由
channel.exchange_declare(exchange="events", exchange_type="topic")

# 绑定队列到不同的路由键模式
channel.queue_bind(exchange="events", queue="order_queue", routing_key="order.*")
channel.queue_bind(exchange="events", queue="payment_queue", routing_key="*.payment")
channel.queue_bind(exchange="events", queue="all_events", routing_key="#")
```

---

## 3. 可靠投递

```python
# 生产者：确认模式
channel.confirm_delivery()  # 开启发布确认
try:
    channel.basic_publish(
        exchange="events",
        routing_key="order.created",
        body=json.dumps(order).encode(),
        properties=pika.BasicProperties(
            delivery_mode=2,  # 持久化消息
            content_type="application/json",
        ),
        mandatory=True,  # 无法路由时返回给生产者
    )
except pika.exceptions.UnroutableError:
    handle_unroutable_message()


# 消费者：手动确认
def callback(ch, method, properties, body):
    try:
        process_message(body)
        ch.basic_ack(delivery_tag=method.delivery_tag)  # 处理完确认
    except Exception:
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)  # 失败重入队


channel.basic_qos(prefetch_count=10)  # 限制未确认消息数
channel.basic_consume(queue="order_queue", on_message_callback=callback, auto_ack=False)
```

`delivery_mode=2` + `basic_ack` + `basic_qos` 三件套缺一不可。

---

## 4. 死信队列（DLQ）

```python
# 死信交换器配置
args = {
    "x-dead-letter-exchange": "dlx_exchange",
    "x-dead-letter-routing-key": "dlq",
    "x-message-ttl": 60000,  # 60 秒超时进 DLQ
}

channel.queue_declare(queue="order_queue", arguments=args)

# 死信队列：单独处理失败消息
channel.queue_declare(queue="dlq")
channel.queue_bind(exchange="dlx_exchange", queue="dlq")
```

死信队列处理策略：
1. 监控 DLQ 消息数，设置告警阈值
2. 写入日志供后续排查
3. 提供重试接口，手动重新投递
4. 超过重试次数转人工处理

---

## 5. 集群部署

```bash
# 节点加入集群
rabbitmqctl stop_app
rabbitmqctl reset
rabbitmqctl join_cluster rabbit@node1
rabbitmqctl start_app
```

```yaml
# 镜像队列（高可用）
channel.queue_declare(
    queue='critical_queue',
    durable=True,
    arguments={
        'x-ha-mode': 'exactly',
        'x-ha-params': 3  # 3 个副本
    }
)
```

RabbitMQ 3.8+ 推荐使用 Quorum Queue 替代镜像队列，基于 Raft 协议，性能更好。

---

## 监控要点

- `queueLength` 持续增长：消费者处理能力不足
- `memory_used` 接近 watermark：触发了 flow control
- `connections` 突增：可能存在连接泄漏

```bash
# 查看队列状态
rabbitmqctl list_queues name messages consumers memory
```

---

## 相关文档

- [[docs/message-queue/kafka|Apache Kafka]] — 高吞吐场景替代
- [[docs/caching/redis|Redis]] — Redis 作为轻量级消息队列
- [[docs/devops/docker|Docker]] — RabbitMQ 容器化部署
- [[docs/monitoring/prometheus-grafana|Prometheus + Grafana]] — RabbitMQ Exporter 监控

---

*本规范随 RabbitMQ 生态演进持续更新。最后更新: 2026-07-20*
