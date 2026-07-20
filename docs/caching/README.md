# 缓存

> 用空间换时间，降低延迟，保护后端服务。

---

## 核心问题

数据库查询慢、重复计算浪费资源、静态资源加载延迟高。

缓存是多层的：应用内存 → Redis → CDN → 浏览器。每一层解决不同维度的问题。

---

## 缓存层次

| 层次 | 工具 | 延迟 | 适合场景 |
|------|------|------|---------|
| L1 进程内 | 内存 Map / LRU Cache | < 1ms | 热点配置、计算结果 |
| L2 分布式 | Redis / Memcached | 1-5ms | 会话、数据库查询缓存 |
| L3 边缘 | CDN（CloudFront / Cloudflare） | 10-50ms | 静态资源、API 缓存 |

选型原则：L1 解决单机热点，L2 解决集群共享，L3 解决地理分布。

---

## 文档索引

- [[docs/caching/redis|Redis]] — 数据结构、缓存模式（Cache-Aside / Write-Through）、过期策略、持久化、哨兵/集群
- [[docs/caching/cdn|CDN 缓存]] — CloudFront / Cloudflare、Cache-Control 头、缓存失效、Origin Shield

---

## 相关文档

- [[docs/database/sql|SQL]] — 数据库查询缓存优化
- [[docs/devops/docker|Docker]] — 缓存服务的容器化部署
- [[docs/monitoring/prometheus-grafana|Prometheus + Grafana]] — 缓存命中率监控
- [[docs/message-queue/kafka|Kafka]] — 缓存失效事件通知

---

*本节覆盖多层缓存策略。最后更新: 2026-07-20*
