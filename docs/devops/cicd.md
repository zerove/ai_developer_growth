---
title: CI/CD Governance Rules
description: > 适用于 CI/CD 流程的 AI Agent 开发规范。
category: 工具层
tags: ['API', 'AI', 'Kubernetes', '测试', '安全']
difficulty: 基础
reading_time: 10 分钟
updated: 2026-07-21
---

# CI/CD Governance Rules

> 适用于 CI/CD 流程的 AI Agent 开发规范。

---

## 1. GitHub Actions

### 工作流结构

```yaml
# ✅ 正确
name: CI/CD

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'
      - run: npm ci
      - run: npm test
      - run: npm run lint

  build:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Build
        run: npm run build
      - name: Upload artifact
        uses: actions/upload-artifact@v4
        with:
          name: build
          path: dist/

  deploy:
    needs: build
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - name: Deploy
        run: echo "Deploying..."
```

### 密钥管理

```yaml
# ✅ 正确: 使用 GitHub Secrets
jobs:
  deploy:
    steps:
      - name: Deploy
        env:
          API_KEY: ${{ secrets.API_KEY }}
          DATABASE_URL: ${{ secrets.DATABASE_URL }}
        run: ./deploy.sh

# ❌ 禁止: 硬编码密钥
jobs:
  deploy:
    steps:
      - name: Deploy
        run: API_KEY=sk-123 ./deploy.sh  # 不安全
```

---

## 2. 质量门禁

### 自动化检查

```yaml
# ✅ 正确: 完整的 CI 流程
jobs:
  quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: npm ci
      
      # 格式检查
      - run: npm run format:check
      
      # Lint 检查
      - run: npm run lint
      
      # 类型检查
      - run: npm run type-check
      
      # 单元测试
      - run: npm run test:unit
      
      # 集成测试
      - run: npm run test:integration
      
      # 安全扫描
      - run: npm audit
      
      # 构建验证
      - run: npm run build
```

### 代码覆盖率

```yaml
# ✅ 正确: 覆盖率检查
jobs:
  coverage:
    runs-on: ubuntu-latest
    steps:
      - run: npm run test:coverage
      - name: Check coverage
        run: |
          COVERAGE=$(cat coverage/coverage-summary.json | jq '.total.lines.pct')
          if (( $(echo "$COVERAGE < 80" | bc -l) )); then
            echo "Coverage below 80%"
            exit 1
          fi
```

---

## 3. 部署策略

### 蓝绿部署

```yaml
# ✅ 正确: 蓝绿部署
jobs:
  deploy:
    steps:
      - name: Deploy to green
        run: |
          kubectl set image deployment/app-green app=myapp:${{ github.sha }}
          kubectl rollout status deployment/app-green
      
      - name: Switch traffic
        run: kubectl patch service app -p '{"spec":{"selector":{"version":"green"}}}'
      
      - name: Cleanup old version
        run: kubectl delete deployment app-blue
```

### 金丝雀发布

```yaml
# ✅ 正确: 金丝雀发布
jobs:
  deploy:
    steps:
      - name: Deploy canary (10%)
        run: |
          kubectl set image deployment/app-canary app=myapp:${{ github.sha }}
          kubectl scale deployment/app-canary --replicas=1
          
      - name: Monitor metrics
        run: sleep 300
      
      - name: Promote to production
        run: |
          kubectl set image deployment/app app=myapp:${{ github.sha }}
          kubectl scale deployment/app --replicas=3
```

---

## 4. 回滚策略

### 自动回滚

```yaml
# ✅ 正确: 配置回滚
jobs:
  deploy:
    steps:
      - name: Deploy
        run: kubectl apply -f k8s/
      
      - name: Verify deployment
        run: |
          kubectl rollout status deployment/app --timeout=300s || \
          kubectl rollout undo deployment/app
```

### 回滚脚本

```bash
#!/bin/bash
# ✅ 正确: 回滚脚本
set -e

DEPLOYMENT=$1
REVISION=${2:-0}

echo "Rolling back $DEPLOYMENT to revision $REVISION"
kubectl rollout undo deployment/$DEPLOYMENT --to-revision=$REVISION
kubectl rollout status deployment/$DEPLOYMENT
```

---

## 5. 监控与告警

### 部署监控

```yaml
# ✅ 正确: 部署后验证
jobs:
  deploy:
    steps:
      - name: Deploy
        run: kubectl apply -f k8s/
      
      - name: Verify health
        run: |
          for i in {1..30}; do
            if curl -f http://app/health; then
              echo "Health check passed"
              exit 0
            fi
            sleep 10
          done
          echo "Health check failed"
          exit 1
      
      - name: Notify success
        if: success()
        run: echo "Deployment successful"
      
      - name: Notify failure
        if: failure()
        run: echo "Deployment failed"
```

---

## 6. 安全扫描

### 依赖扫描

```yaml
# ✅ 正确: 依赖安全扫描
jobs:
  security:
    runs-on: ubuntu-latest
    steps:
      - run: npm audit --audit-level=high
      
      - name: Snyk scan
        uses: snyk/actions/node@master
        env:
          SNYK_TOKEN: ${{ secrets.SNYK_TOKEN }}
```

### 镜像扫描

```yaml
# ✅ 正确: 容器镜像扫描
jobs:
  image-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Build image
        run: docker build -t myapp:${{ github.sha }} .
      
      - name: Scan with Trivy
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: 'myapp:${{ github.sha }}'
          format: 'table'
          exit-code: '1'
          severity: 'CRITICAL,HIGH'
```

---

## 7. 质量检查清单

### 流程

- [ ] CI 流程完整
- [ ] 质量门禁配置
- [ ] 部署策略定义
- [ ] 回滚机制

### 安全

- [ ] 密钥管理
- [ ] 依赖扫描
- [ ] 镜像扫描
- [ ] 访问控制

### 监控

- [ ] 部署监控
- [ ] 健康检查
- [ ] 告警配置
- [ ] 日志收集

---

*本规范随 CI/CD 生态演进持续更新。最后更新: 2026-07-17*
