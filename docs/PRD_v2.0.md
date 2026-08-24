# JCode AI-Native SDLC Platform - 产品需求文档 (PRD v2.0)

> **版本**: 2.0 (工业化产品级)
> **状态**: 规划中
> **目标**: 从"代码级工具链"升级为"企业级 AI-Native SDLC 平台"

---

## 1. 产品愿景

**JCode AI-Native SDLC Platform** 是面向 AI 时代的软件工程平台，将 AI 融入软件全生命周期（需求→设计→编码→测试→部署→运维→复盘），实现：
- **AI 原生**: 全流程 AI 协作，人机共创
- **工程化**: 标准化、可度量、可复现、可审计
- **自治化**: 自愈、自优化、自演进

---

## 2. 目标用户与场景

| 用户画像 | 核心需求 | 关键场景 |
|----------|----------|----------|
| **平台工程团队** | 标准化工程实践、治理合规 | 多团队统一流程、审计追溯 |
| **应用开发团队** | 高效交付、质量内建 | 特性分支→MR→自动部署→监控 |
| **架构师/技术负责人** | 架构守护、技术债管理 | 架构漂移检测、技术债可视化 |
| **SRE/运维团队** | 可观测性、故障自愈 | 混沌演练、自动熔断、回滚 |
| **管理层/PO** | 交付度量、风险预警 | 迭代仪表板、预测性分析 |

---

## 3. 核心功能模块 (MVP → v2.0)

### 3.1 已完成 (v1.0 基座)
- [x] **DoR 意图验证** - 7 点评分卡
- [x] **AI-Native 工作流** - 4 步编排 (DoR→语义图/架构→红蓝辩论/作用域→遥测/审计)
- [x] **语义代码图谱** - AST 级依赖分析 O(n) 优化
- [x] **AI 质量门禁** - 反模式/命名/阈值/安全/幻觉检测
- [x] **红蓝对抗审查** - 多 Agent 辩论 + 作用域守卫
- [x] **统一 Hook 运行器** - lint/format/typecheck/test/security/quality-gate/governance
- [x] **架构漂移守卫** - 分层架构合规检查
- [x] **遥测与审计账本** - 加密链式记录

### 3.2 v2.0 核心增量 (本规划重点)

| 模块 | 子功能 | 验收标准 |
|------|--------|----------|
| **Release Automation** | 语义化版本、自动 CHANGELOG、Docker/SBOM、签名验证 | `make release` 单命令完成全流程 |
| **GitOps 部署** | Helm Chart、ArgoCD、蓝绿/金丝雀、自动回滚 | `make deploy-prod` 零停机发布 |
| **Issue/MR 自动化** | GitHub Projects 双向同步、MR 检查清单、Dependabot 集成 | 零手工同步、MR 通过率 > 95% |
| **监控告警体系** | Prometheus Operator、Grafana、Alertmanager、SLO/SLI、烧钱率告警 | 4 个关键指标 100% 覆盖 |
| **混沌工程** | Chaos Mesh、网络/CPU/内存/时钟故障注入、自动恢复验证 | 月度演练 100% 通过 |
| **性能预算门禁** | 基准回归自动对比、性能回归阻断 CI、趋势分析 | 回归 > 10% 即阻断 |
| **自动化复盘** | 迭代指标收集、AI 生成报告、知识沉淀至案例库 | 每迭代自动生成 |
| **全链路验证** | E2E/契约/混沌/发布演练、混沌游戏日 | 零严重缺陷发布 |

---

## 4. 技术栈选型 (v2.0)

| 层级 | 选型 | 理由 |
|------|------|------|
| **核心语言** | Python 3.11+ / Go 1.22+ | AI 生态成熟 / 高性能服务 |
| **容器编排** | Kubernetes 1.28+ / Helm 3.12+ | 行业标准、生态完善 |
| **GitOps** | ArgoCD / Flux v2 | 声明式、可审计、自愈 |
| **Service Mesh** | Istio / Linkerd | mTLS、流量管理、可观测 |
| **监控栈** | Prometheus Operator + Grafana + Alertmanager + Thanos | CNCF 毕业项目、长期支持 |
| **日志/追踪** | Loki + Tempo + OpenTelemetry | 统一三大支柱 |
| **混沌工程** | Chaos Mesh / Litmus | Kubernetes 原生、CRD 管理 |
| **SBOM/签名** | Syft / Cosign / Rekor | 供应链安全标准 |
| **策略引擎** | OPA / Kyverno | 准入控制、合规自动化 |
| **AI 集成** | LangGraph / AutoGen / 本地 LLM (Ollama) | 可插拔、数据不出域 |

---

## 5. 架构设计

```
┌─────────────────────────────────────────────────────────────────┐
│                        JCode Platform v2.0                      │
├─────────────────────────────────────────────────────────────────┤
│  CLI / API Gateway (jcode-cli, REST/gRPC)                       │
├─────────────────────────────────────────────────────────────────┤
│  Orchestration Layer (工作流编排、状态机、补偿事务)              │
├──────────────┬──────────────┬──────────────┬──────────────────┤
│  Plan &      │  Code &      │  Deploy &    │  Observe &       │
│  Govern      │  Quality     │  Operate     │  Improve         │
├──────────────┼──────────────┼──────────────┼──────────────────┤
│ DoR/ADR      │ Quality Gate │ GitOps/ArgoCD│ Prometheus/      │
│ Architecture │ (规则引擎)    │ (ArgoCD)     │ Grafana/Loki/    │
│ Guard        │ PR Review    │ Canary/Blue- │ Tempo            │
│ Policy/OPA   │ SBOM/Sign    │ Green        │ Alertmanager     │
│ Issue Sync   │ Chaos Mesh   │ Rollback     │ SLO/SLI          │
└──────────────┴──────────────┴──────────────┴──────────────────┘
          │            │            │             │
          └────────────┴────────────┴─────────────┘
                    │
          ┌─────────┴─────────┐
          │  Data & Knowledge │
          │  - Semantic Graph │
          │  - Audit Ledger   │
          │  - Case Library   │
          │  - Metrics DB     │
          └───────────────────┘
```

---

## 5. 里程碑计划

| 里程碑 | 时间周期 | 交付物 | 验收标准 |
|--------|----------|--------|----------|
| **M1: Release & Deploy 基建** | Week 1-2 | Release 自动化、Helm Chart、ArgoCD、基础监控 | `make release/deploy` 单命令跑通 |
| **M2: Issue/MR + 监控闭环** | Week 3-4 | Issue 同步、MR 清单、Prometheus/Grafana/SLO、告警 | 零手工同步、4 关键指标 100% 覆盖 |
| **M3: 混沌/性能/复盘** | Week 5-6 | Chaos Mesh、性能预算、自动复盘、混沌演练 | 月度演练 100% 通过 |
| **M4: 全链路验证 & 发布** | Week 7 | E2E/契约/混沌/发布演练、文档、培训 | 零严重缺陷、文档完整 |

---

## 6. 非功能性需求 (NFR)

| 指标 | 目标 | 测量方式 |
|------|------|----------|
| **可用性** | 99.95% (SLA) | Prometheus 统计 |
| **部署频次** | 随需部署 (日均 > 10) | ArgoCD 统计 |
| **变更前置时间** | < 30 min (代码→生产) | CI/CD 计时 |
| **平均恢复时间** | < 15 min (MTTR) | 混沌演练实测 |
| **变更失败率** | < 5% | 事故统计 |
| **安全合规** | SLSA Level 3、SBOM 100% | 供应链审计 |
| **性能预算** | P95 < 200ms、吞吐 > 1000 RPS | 基准回归 |

---

## 7. 团队与角色

| 角色 | 职责 | 人员配置 |
|------|------|----------|
| **Platform Engineer** | 基础设施、CI/CD、GitOps | 2 |
| **Backend Engineer** | 核心服务、API、数据模型 | 2 |
| **AI/ML Engineer** | Agent 编排、规则引擎、AI 审查 | 1 |
| **SRE** | 监控、混沌、容量规划、事件响应 | 1 |
| **Security Engineer** | 供应链、策略、审计、渗透测试 | 1 (兼职) |
| **Technical Writer** | 文档、Runbook、培训材料 | 0.5 (兼职) |
| **Engineering Manager** | 规划、协调、风险、交付 | 1 |

---

## 8. 风险与缓解

| 风险 | 等级 | 缓解措施 |
|------|------|----------|
| ArgoCD/Helm 学习曲线 | 高 | 内部培训、Pair Programming、Runbook |
| 混沌工程影响生产 | 高 | 仅 Staging、自动熔断、游戏日预演 |
| AI 审查误报/漏报 | 中 | 人工复核机制、持续微调、人工兜底 |
| 供应链攻击面 | 高 | SLSA L3、SBOM、签名验证、依赖扫描 |
| 技术债累积 | 中 | 架构守卫、定期重构周、ADR 强制 |

---

## 8. 附录：当前差距矩阵

| 能力域 | 当前 | 目标 | 差距 | 优先级 |
|--------|------|------|------|--------|
| Release 自动化 | 手工 CHANGELOG | 全自动 + SBOM + 签名 | 大 | P0 |
| 部署 | 手工/脚本 | GitOps + 金丝雀 | 大 | P0 |
| Issue 追踪 | 无 | 双向同步 | 中 | P1 |
| 监控告警 | 基础 | SLO/SLI + 多维告警 | 中 | P1 |
| 混沌工程 | 无 | 定期演练 + 自动验证 | 中 | P1 |
| 性能预算 | 手工基线 | CI 门禁 + 自动对比 | 小 | P1 |
| 复盘报告 | 手工 | 自动生成 + 沉淀 | 小 | P2 |

---

**批准**: ________________ **日期**: ________________
