# Kubernetes Governance Rules

> 适用于 Kubernetes 项目的 AI Agent 开发规范。

---

## 1. 部署规范

### Deployment 配置

```yaml
# ✅ 正确
apiVersion: apps/v1
kind: Deployment
metadata:
  name: user-service
  labels:
    app: user-service
spec:
  replicas: 3
  selector:
    matchLabels:
      app: user-service
  template:
    metadata:
      labels:
        app: user-service
    spec:
      containers:
      - name: user-service
        image: myapp/user-service:1.0.0
        ports:
        - containerPort: 3000
        resources:
          requests:
            memory: "128Mi"
            cpu: "100m"
          limits:
            memory: "256Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health
            port: 3000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 3000
          initialDelaySeconds: 5
          periodSeconds: 5
```

### 禁止行为

```yaml
# ❌ 禁止: 无资源限制
spec:
  containers:
  - name: app
    image: myapp:latest  # 无资源限制，可能导致节点不稳定

# ❌ 禁止: 无健康检查
spec:
  containers:
  - name: app
    image: myapp:latest  # 无探针，无法知道容器状态
```

---

## 2. 服务发现

### Service 配置

```yaml
# ✅ 正确: ClusterIP 服务
apiVersion: v1
kind: Service
metadata:
  name: user-service
spec:
  selector:
    app: user-service
  ports:
  - port: 80
    targetPort: 3000
  type: ClusterIP

# ✅ 正确: LoadBalancer 服务
apiVersion: v1
kind: Service
metadata:
  name: user-service-lb
spec:
  selector:
    app: user-service
  ports:
  - port: 80
    targetPort: 3000
  type: LoadBalancer
```

---

## 3. 配置管理

### ConfigMap

```yaml
# ✅ 正确
apiVersion: v1
kind: ConfigMap
metadata:
  name: user-service-config
data:
  NODE_ENV: "production"
  LOG_LEVEL: "info"

# Deployment 中使用
spec:
  containers:
  - name: app
    envFrom:
    - configMapRef:
        name: user-service-config
```

### Secret

```yaml
# ✅ 正确
apiVersion: v1
kind: Secret
metadata:
  name: user-service-secrets
type: Opaque
data:
  DATABASE_URL: cG9zdGdyZXNxbDovL3VzZXI6cGFzc3dvcmRAZGI6NTQzMi9teWFwcA==
  API_KEY: c2stMTIzNDU2Nzg5MA==

# Deployment 中使用
spec:
  containers:
  - name: app
    envFrom:
    - secretRef:
        name: user-service-secrets
```

---

## 4. Ingress 配置

### Ingress 规则

```yaml
# ✅ 正确
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: user-service-ingress
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  tls:
  - hosts:
    - api.example.com
    secretName: api-tls
  rules:
  - host: api.example.com
    http:
      paths:
      - path: /users
        pathType: Prefix
        backend:
          service:
            name: user-service
            port:
              number: 80
```

---

## 5. 水平扩展

### HPA 配置

```yaml
# ✅ 正确
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: user-service-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: user-service
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

---

## 6. 网络策略

### NetworkPolicy

```yaml
# ✅ 正确: 限制入站流量
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: user-service-netpol
spec:
  podSelector:
    matchLabels:
      app: user-service
  policyTypes:
  - Ingress
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: api-gateway
    ports:
    - protocol: TCP
      port: 3000
```

---

## 7. 测试规范

### 集成测试

```bash
# ✅ 正确: 使用 kind 进行本地测试
kind create cluster --name test
kubectl apply -f k8s/
kubectl get pods  # 验证部署
curl http://localhost/users  # 验证服务
kind delete cluster --name test
```

### 端到端测试

```bash
# ✅ 正确: 使用 kubectl 验证
kubectl rollout status deployment/user-service
kubectl logs deployment/user-service
kubectl exec -it pod/user-service-xxx -- curl localhost:3000/health
```

---

## 8. 质量检查清单

### 部署

- [ ] Deployment 配置完整
- [ ] 资源限制配置
- [ ] 健康检查配置
- [ ] 环境变量管理

### 网络

- [ ] Service 配置正确
- [ ] Ingress 规则完整
- [ ] NetworkPolicy 配置
- [ ] TLS 配置

### 安全

- [ ] Secrets 管理
- [ ] RBAC 配置
- [ ] Pod 安全策略
- [ ] 镜像来源验证

---

*本规范随 Kubernetes 生态演进持续更新。最后更新: 2026-07-17*
