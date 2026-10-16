---
title: 监控
description: > 没有监控的系统是黑盒。线上出了问题，你只能祈祷。
category: 工具层
tags: ['Docker', 'Kubernetes']
difficulty: 基础
reading_time: 10 分钟
updated: 2026-07-21
---

# 监控

> 没有监控的系统是黑盒。线上出了问题，你只能祈祷。

---

## 核心问题

服务挂了不知道、性能劣化发现迟、出了问题无法定位根因。

监控的三大支柱：指标（Metrics）、日志（Logs）、链路追踪（Traces）。本节覆盖前两者。

---

## 监控体系

| 层次 | 工具 | 解决什么 |
|------|------|---------|
| 指标 | Prometheus + Grafana | 系统状态、趋势、告警 |
| 日志 | ELK / Loki | 事件排查、审计 |
| 追踪 | Jaeger / Tempo | 跨服务调用链路 |

---

## 文档索引

- [[docs/monitoring/prometheus-grafana|Prometheus + Grafana]] — 指标采集、告警规则、仪表盘设计、Exporter
- [[docs/monitoring/logging|集中化日志]] — ELK Stack、Loki、结构化日志
- [[docs/monitoring/ai-audit-live|AI-Native 实时审计看板]] — 实时展示 AI-Native 审计结果

---

## 相关文档

- [[docs/devops/docker|Docker]] — 容器监控配置
- [[docs/devops/kubernetes|Kubernetes]] — K8s 监控栈（metrics-server、kube-state-metrics）
- [[docs/message-queue/kafka|Kafka]] — 消息队列监控指标
- [[docs/caching/redis|Redis]] — Redis Exporter 配置

---

## 监控原则

1. **告警要可操作**: 收到告警后能立刻行动，否则就是噪音
2. **四个黄金信号**: 延迟、流量、错误率、饱和度（来自 Google SRE）
3. **SLO 驱动**: 定义服务水平目标，告警基于 SLO 违反而非单个指标
4. **渐进式**: 先监控关键路径，再逐步覆盖

---

*本节覆盖监控基础设施的最佳实践。最后更新: 2026-07-20*
