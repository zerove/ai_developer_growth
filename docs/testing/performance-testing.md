---
title: 性能测试指南
description: > 负载、压力、容量、稳定性测试的工具选型、指标定义、基线建立与回归防护。
category: 工具层
tags: ['AI', 'API', 'performance', '测试', 'SQL']
difficulty: 基础
reading_time: 10 分钟
updated: 2026-07-21
---

# 性能测试指南

> 负载、压力、容量、稳定性测试的工具选型、指标定义、基线建立与回归防护。

---

## 1. 测试类型对比

| 类型 | 目标 | 负载模式 | 持续时间 | 关注指标 |
|------|------|----------|----------|----------|
| **负载测试** | 验证预期负载下性能 | 逐步增至预期峰值 | 30-60 min | P99 延迟、吞吐、错误率 |
| **压力测试** | 寻找断点 | 超过峰值至崩溃 | 至系统失效 | 最大 QPS、资源饱和点 |
| **容量测试** | 规划扩容 | 长时间恒定负载 | 4-8 小时 | 内存泄漏、GC、连接池 |
| **稳定性/浸泡** | 长期运行可靠性 | 正常业务负载 | 24-72 小时 | 无内存泄漏、无连接泄漏 |
| **尖峰测试** | 突发流量应对 | 瞬间峰值 | 5-10 min | 熔断、限流、自动扩容 |

---

## 2. 核心指标定义

| 指标 | 计算 | 健康阈值 (参考) |
|------|------|-----------------|
| **QPS/TPS** | 成功请求数 / 秒 | 业务预期峰值 × 1.5 |
| **P50/P95/P99 延迟** | 响应时间分位数 | P99 < 500ms (API), < 2s (页面) |
| **错误率** | 失败请求 / 总请求 | < 0.1% (核心), < 1% (非核心) |
| **吞吐量** | MB/s 或 请求/秒 | 网卡/带宽 < 70% |
| **资源利用率** | CPU/内存/磁盘/网络 | CPU < 70%, 内存 < 80% |
| **连接池使用率** | 活跃连接 / 最大连接 | < 80% |

---

## 3. 工具选型

| 场景 | 推荐工具 | 特点 |
|------|----------|------|
| **API/微服务** | **k6**, Locust, JMeter | 代码化、CI 集成好、支持协议多 |
| **Web UI** | Playwright, Cypress | 真实浏览器、含渲染时间 |
| **数据库** | sysbench, pgbench | 纯 DB 压测 |
| **消息队列** | 自写 Producer/Consumer | 验证吞吐与延迟 |
| **全链路** | k6 + Grafana k6 | 可视化、阈值告警 |

**首选 k6**：TypeScript/JS 编写、单二进制、Grafana 原生、CI 友好。

---

## 4. k6 实战模板

```javascript
// load-test.js
import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate } from 'k6/metrics';

const errorRate = new Rate('errors');

export const options = {
  stages: [
    { duration: '2m', target: 100 },  // 预热
    { duration: '5m', target: 500 },  // 正常负载
    { duration: '2m', target: 1000 }, // 峰值
    { duration: '5m', target: 1000 }, // 持续峰值
    { duration: '2m', target: 0 },    // 降温
  ],
  thresholds: {
    http_req_duration: ['p(95)<500', 'p(99)<1000'],
    http_req_failed: ['rate<0.01'],
    errors: ['rate<0.01'],
  },
};

const BASE_URL = __ENV.BASE_URL || 'https://api.example.com';
const TOKEN = __ENV.AUTH_TOKEN;

export default function () {
  const headers = {
    'Authorization': `Bearer ${TOKEN}`,
    'Content-Type': 'application/json',
  };

  // 场景 1: 列表查询 (高频)
  let res = http.get(`${BASE_URL}/api/v1/orders?page=1&size=20`, { headers });
  check(res, { 'list status 200': (r) => r.status === 200 });
  errorRate.add(res.status !== 200);

  sleep(1);

  // 场景 2: 详情查询 (中频)
  res = http.get(`${BASE_URL}/api/v1/orders/12345`, { headers });
  check(res, { 'detail status 200': (r) => r.status === 200 });

  sleep(2);

  // 场景 3: 创建订单 (低频、写入)
  const payload = JSON.stringify({ product_id: 999, qty: 1 });
  res = http.post(`${BASE_URL}/api/v1/orders`, payload, { headers });
  check(res, { 'create status 201': (r) => r.status === 201 });
  errorRate.add(res.status !== 201);
}
```

**运行**：
```bash
BASE_URL=https://staging.api.com AUTH_TOKEN=xyz k6 run load-test.js
```

---

## 5. CI 集成策略

```yaml
# .github/workflows/perf.yml
jobs:
  performance:
    runs-on: ubuntu-latest
    if: github.event_name == 'schedule' || github.event_name == 'workflow_dispatch'
    steps:
      - uses: actions/checkout@v4
      - name: Run k6
        uses: grafana/k6-action@v0.2
        with:
          filename: tests/perf/load-test.js
          env: |
            BASE_URL=${{ secrets.STAGING_API }}
            AUTH_TOKEN=${{ secrets.PERF_TOKEN }}
      - name: Upload results
        uses: actions/upload-artifact@v4
        with:
          name: k6-results
          path: results.json
```

**频率**：
- 每日定时跑基准负载
- 发布前跑完整压测
- 主分支合并后可选跑轻量烟雾测试

---

## 6. 基线管理与回归

### 建立基线
1. 首次跑测 → 导出 JSON 结果
2. 提交 `perf-baseline.json` 到仓库
3. 标记版本号

### 回归检测
```javascript
// 在 k6 脚本中引用基线
import { baseline } from './perf-baseline.json';

export const options = {
  thresholds: {
    http_req_duration: [
      `p(95)<${baseline.p95 * 1.2}`,  // 允许 20% 抖动
      `p(99)<${baseline.p99 * 1.2}`,
    ],
  },
};
```

### 可视化
- **Grafana k6 Dashboard** 实时看板
- **GitHub PR Comment** 自动对比本次 vs 基线

---

## 7. 常见性能反模式

| 反模式 | 症状 | 定位方法 |
|--------|------|----------|
| N+1 查询 | QPS 上不去、DB CPU 高 | EXPLAIN ANALYZE、慢查询日志 |
| 连接池耗尽 | 报错 "pool exhausted" | 监控连接池指标、调整大小 |
| 无限制分页 | 翻页越深越慢 | Cursor-based pagination |
| 同步阻塞 I/O | CPU 低但 QPS 上不去 | flamegraph、async/await |
| 缓存击穿 | 瞬间 DB 压垮 | 互斥锁重建、空值缓存 |
| 大对象序列化 | GC 频繁、延迟抖动 | protobuf/flatbuffers、分批 |

---

## 8. 数据库专项压测

```bash
# PostgreSQL: pgbench
pgbench -i -s 50 testdb          # 初始化 50 倍规模 (~500万行)
pgbench -c 50 -j 4 -T 300 testdb # 50 并发、4 线程、跑 5 分钟

# MySQL: sysbench
sysbench oltp_read_write --db-driver=mysql --mysql-db=testdb \
  --tables=10 --table-size=1000000 prepare
sysbench oltp_read_write --threads=64 --time=300 run
```

**关注**：TPS、延迟分位、死锁率、复制延迟。

---

## 9. 质量清单

- [ ] 测试脚本版本控制，随代码演进
- [ ] 测试数据隔离（不污染共享环境）
- [ ] 阈值配置为代码，而非硬编码在 CI
- [ ] 结果可追溯（每次跑测生成报告归档）
- [ ] 关键路径有告警（P99 超基线 20% 即报警）
- [ ] 定期（月度）重跑基线校准

---

*性能测试不是一次性活动，而是持续的回归防线。最后更新: 2026-07-20*
