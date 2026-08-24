# JCode Platform Helm Chart

JCode AI-Native SDLC Platform 的 Kubernetes 部署 Helm Chart。

## 快速开始

### 前置要求
- Kubernetes 1.28+
- Helm 3.12+
- 容器镜像仓库访问权限
- cert-manager 已安装（用于 TLS 证书）
- Prometheus Operator 已安装（用于监控）

### 安装

```bash
# 添加依赖的 Helm 仓库
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add grafana https://grafana.github.io/helm-charts
helm repo add chaos-mesh https://charts.chaos-mesh.org
helm repo update

# 安装 CRDs (Prometheus Operator, Chaos Mesh)
kubectl apply -f https://github.com/prometheus-operator/prometheus-operator/releases/latest/download/bundle.yaml
kubectl apply -f https://charts.chaos-mesh.org/manifests/crds.yaml

# 创建命名空间
kubectl create namespace production

# 创建镜像拉取 Secret
kubectl create secret docker-registry registry-credentials \
  --docker-server=registry.example.com \
  --docker-username=<username> \
  --docker-password=<password> \
  --namespace production

# 安装
helm install jcode-platform ./helm/jcode-platform \
  -f values.yaml -f values-prod.yaml \
  --namespace production --create-namespace
```

### 配置

#### 必需配置

| 参数 | 说明 | 默认值 |
|--------|------|--------|
| `global.imageRegistry` | 镜像仓库地址 | `registry.example.com` |
| `global.imagePullSecrets` | 镜像拉取 Secret | `registry-credentials` |

#### 环境配置文件

| 环境 | 配置文件 | 说明 |
|------|----------|------|
| Staging | `values-staging.yaml` | 单副本、资源受限、启用混沌工程 |
| Production | `values-prod.yaml` | 高可用、资源充足、严格安全 |

### 组件

| 组件 | 说明 | 默认启用 |
|------|------|----------|
| `api` | API Server / Orchestrator 入口 | ✅ |
| `orchestrator` | 工作流编排引擎 | ✅ |
| `qualityGate` | AI 质量门禁 | ✅ |
| `semantic` | 语义代码图谱 | ✅ |
| `audit` | 审计账本 | ✅ |
| `chaos` | 混沌工程 | ❌ (仅 Staging) |
| `retro` | 自动化复盘 | ✅ |

### 监控

默认部署完整监控栈：
- Prometheus + Alertmanager + Grafana
- Loki (日志)
- Tempo (追踪)
- ServiceMonitor + PrometheusRule

### 升级

```bash
helm upgrade jcode-platform ./helm/jcode-platform \
  -f values.yaml -f values-prod.yaml \
  --namespace production
```

### 卸载

```bash
helm uninstall jcode-platform --namespace production
```

## 配置参数

### 全局参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `global.imageRegistry` | string | `registry.example.com` | 镜像仓库地址 |
| `global.imagePullSecrets` | list | `[{name: registry-credentials}]` | 镜像拉取 Secret |
| `global.resources` | object | 见 values.yaml | 默认资源配额 |

### 组件参数

每个组件支持以下通用参数：

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `enabled` | bool | `true` | 是否启用 |
| `replicaCount` | int | 组件特定 | 副本数 |
| `resources` | object | 组件特定 | 资源限制/请求 |
| `autoscaling.enabled` | bool | `true` | 是否启用 HPA |
| `autoscaling.minReplicas` | int | 组件特定 | 最小副本数 |
| `autoscaling.maxReplicas` | int | 组件特定 | 最大副本数 |

### 监控参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `monitoring.enabled` | bool | `true` | 启用监控栈 |
| `monitoring.prometheus.enabled` | bool | `true` | 启用 Prometheus |
| `monitoring.grafana.enabled` | bool | `true` | 启用 Grafana |
| `loki.enabled` | bool | `true` | 启用 Loki |
| `tempo.enabled` | bool | `true` | 启用 Tempo |

### Ingress 参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `ingress.enabled` | bool | `true` | 启用 Ingress |
| `ingress.className` | string | `nginx` | Ingress Class |
| `ingress.annotations` | object | 见 values.yaml | Ingress 注解 |
| `ingress.tls` | list | 见 values.yaml | TLS 配置 |

### 安全参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `security.podSecurityStandards` | string | `restricted` | Pod Security Standard |
| `security.networkPolicies.enabled` | bool | `true` | 启用 NetworkPolicy |
| `security.networkPolicies.defaultDeny` | bool | `true` | 默认拒绝 |

### 自动扩缩容

```yaml
autoscaling:
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
        - type: Percent
          value: 10
          periodSeconds: 60
    scaleUp:
      stabilizationWindowSeconds: 0
      policies:
        - type: Percent
          value: 100
          periodSeconds: 15
        - type: Pods
          value: 4
          periodSeconds: 15
      selectPolicy: Max
```

## 部署示例

### 生产环境部署

```bash
# 1. 创建命名空间
kubectl create namespace production

# 2. 创建镜像拉取 Secret
kubectl create secret docker-registry registry-credentials \
  --docker-server=registry.example.com \
  --docker-username=<username> \
  --docker-password=<password> \
  --namespace production

# 3. 创建 TLS 证书 Secret (或使用 cert-manager)
kubectl create secret tls jcode-platform-tls-prod \
  --cert=path/to/tls.crt \
  --key=path/to/tls.key \
  --namespace production

# 4. 创建敏感配置 Secret
kubectl create secret generic jcode-platform-secrets \
  --from-literal=postgresql-password=<password> \
  --from-literal=redis-password=<password> \
  --from-literal=registry-username=<username> \
  --from-literal=registry-password=<password> \
  --from-literal=slack-webhook-url=<url> \
  --from-literal=github-token=<token> \
  --namespace production

# 5. 安装 Chart
helm install jcode-platform ./helm/jcode-platform \
  -f values.yaml -f values-prod.yaml \
  --namespace production --create-namespace \
  --wait --timeout 10m
```

### 验证部署

```bash
# 检查 Pod 状态
kubectl get pods -n production -l app.kubernetes.io/instance=jcode-platform

# 检查服务
kubectl get svc -n production

# 检查 Ingress
kubectl get ingress -n production

# 检查监控
kubectl get servicemonitor,prometheusrule -n production
```

### 常用操作

```bash
# 查看日志
kubectl logs -n production -l app.kubernetes.io/component=api -f

# 查看 Pod 详情
kubectl describe pod -n production -l app.kubernetes.io/component=api

# 重启部署
kubectl rollout restart deployment/jcode-platform-api -n production

# 查看发布历史
helm history jcode-platform -n production

# 回滚
helm rollback jcode-platform <revision> -n production

# 卸载
helm uninstall jcode-platform -n production
```

## 故障排查

### 常见问题

1. **镜像拉取失败**
   - 检查 `imagePullSecrets` 配置
   - 验证 Registry 凭据
   - 检查镜像是否存在

2. **Pod 启动失败**
   - `kubectl describe pod <pod-name> -n production`
   - 查看事件: `kubectl get events -n production --sort-by='.lastTimestamp'`

3. **监控数据缺失**
   - 检查 ServiceMonitor 是否创建: `kubectl get servicemonitor -n production`
   - 检查 Prometheus 目标: `kubectl port-forward -n monitoring svc/prometheus-operated 9090:9090`

3. **Ingress 不生效**
   - 检查 Ingress Controller 状态
   - 验证 TLS 证书: `kubectl get secret -n production`

### 日志查看

```bash
# API 服务日志
kubectl logs -n production -l app.kubernetes.io/component=api -f

# Orchestrator 日志
kubectl logs -n production -l app.kubernetes.io/component=orchestrator -f

# 查看所有组件日志
kubectl logs -n production -l app.kubernetes.io/instance=jcode-platform --all-containers=true -f
```

## 许可证

MIT License

## 贡献

欢迎提交 Issue 和 PR！
