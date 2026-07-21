---
title: Docker Governance Rules
description: > 适用于 Docker 项目的 AI Agent 开发规范。
category: 工具层
tags: ['API', 'AI', '测试', 'SQL', '部署']
difficulty: 初级
reading_time: 10 分钟
updated: 2026-07-21
---

# Docker Governance Rules

> 适用于 Docker 项目的 AI Agent 开发规范。

---

## 1. Dockerfile 规范

### 多阶段构建

```dockerfile
# ✅ 正确: 多阶段构建
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/node_modules ./node_modules
COPY package*.json ./

EXPOSE 3000
CMD ["npm", "start"]
```

### 优化层缓存

```dockerfile
# ✅ 正确: 先复制依赖文件
COPY package*.json ./
RUN npm ci
COPY . .

# ❌ 禁止: 先复制所有文件
COPY . .
RUN npm ci  # 每次代码变更都会重新安装依赖
```

### 最小化镜像

```dockerfile
# ✅ 正确: 使用 Alpine
FROM node:20-alpine

# ❌ 禁止: 使用完整镜像
FROM node:20  # 镜像过大
```

---

## 2. 镜像安全

### 非 root 用户

```dockerfile
# ✅ 正确: 创建非 root 用户
RUN addgroup -g 1001 -S appgroup
RUN adduser -S appuser -u 1001
USER appuser

# ❌ 禁止: 使用 root
USER root  # 安全风险
```

### 扫描漏洞

```bash
# ✅ 正确: 使用 Trivy 扫描
trivy image myapp:latest

# ❌ 禁止: 忽略安全扫描
docker build -t myapp .  # 直接构建，不扫描
```

---

## 3. Docker Compose

### 开发环境

```yaml
# ✅ 正确: docker-compose.yml
version: '3.8'

services:
  app:
    build:
      context: .
      dockerfile: Dockerfile.dev
    volumes:
      - .:/app
      - /app/node_modules
    ports:
      - "3000:3000"
    environment:
      - NODE_ENV=development
    depends_on:
      - db
      - redis

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: myapp
      POSTGRES_USER: user
      POSTGRES_PASSWORD: password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

volumes:
  postgres_data:
```

### 生产环境

```yaml
# ✅ 正确: 生产配置
version: '3.8'

services:
  app:
    image: myapp:${VERSION}
    deploy:
      replicas: 3
      resources:
        limits:
          cpus: '0.5'
          memory: 512M
    environment:
      - NODE_ENV=production
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

---

## 4. 网络配置

### 自定义网络

```yaml
# ✅ 正确: 使用自定义网络
services:
  app:
    networks:
      - frontend
      - backend

  db:
    networks:
      - backend

networks:
  frontend:
  backend:
```

### 服务发现

```yaml
# ✅ 正确: 使用服务名
services:
  app:
    environment:
      - DATABASE_URL=postgres://user:password@db:5432/myapp
      - REDIS_URL=redis://redis:6379
```

---

## 5. 数据管理

### 卷挂载

```yaml
# ✅ 正确: 使用命名卷
services:
  db:
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:  # 命名卷，持久化数据

# ❌ 禁止: 使用匿名卷
volumes:
  - /var/lib/postgresql/data  # 匿名卷，难以管理
```

### 备份策略

```bash
# ✅ 正确: 定期备份
docker exec postgres pg_dump -U user myapp > backup_$(date +%Y%m%d).sql
```

---

## 6. 环境变量

### Secrets 管理

```yaml
# ✅ 正确: 使用 Docker secrets
services:
  app:
    secrets:
      - db_password
      - api_key

secrets:
  db_password:
    file: ./secrets/db_password.txt
  api_key:
    file: ./secrets/api_key.txt

# ❌ 禁止: 硬编码密码
environment:
  - DATABASE_URL=postgres://user:password@db:5432/myapp  # 不安全
```

### 环境文件

```bash
# ✅ 正确: 使用 .env 文件
docker-compose --env-file .env.prod up -d

# .env.example (模板)
DATABASE_URL=postgres://user:password@localhost:5432/myapp
REDIS_URL=redis://localhost:6379
API_KEY=your-api-key-here
```

---

## 7. 测试规范

### 容器测试

```bash
# ✅ 正确: 测试镜像构建
docker build -t myapp:test .
docker run --rm myapp:test npm test

# ✅ 正确: 测试容器运行
docker-compose -f docker-compose.test.yml up --abort-on-container-exit
```

### 集成测试

```bash
# ✅ 正确: 使用测试环境
docker-compose -f docker-compose.yml -f docker-compose.test.yml up -d
npm run test:integration
docker-compose down
```

---

## 8. 性能优化

### 镜像大小

```dockerfile
# ✅ 正确: 清理缓存
RUN npm ci && npm cache clean --force

# ✅ 正确: 使用 .dockerignore
# .dockerignore
node_modules
.git
*.md
.env*
```

### 构建缓存

```bash
# ✅ 正确: 使用 BuildKit
DOCKER_BUILDKIT=1 docker build -t myapp .

# ✅ 正确: 挂载缓存
docker build --mount=type=cache,target=/root/.npm -t myapp .
```

---

## 9. 质量检查清单

### Dockerfile

- [ ] 使用多阶段构建
- [ ] 使用 Alpine 基础镜像
- [ ] 非 root 用户运行
- [ ] 优化层缓存
- [ ] 添加健康检查

### Docker Compose

- [ ] 使用命名卷
- [ ] 使用自定义网络
- [ ] 环境变量管理
- [ ] 资源限制配置

### 安全

- [ ] 镜像漏洞扫描
- [ ] Secrets 管理
- [ ] 无硬编码密码
- [ ] 最小权限原则

---

*本规范随 Docker 生态演进持续更新。最后更新: 2026-07-17*
