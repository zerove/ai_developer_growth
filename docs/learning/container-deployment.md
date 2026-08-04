---
title: 容器化部署
description: Docker 容器化部署的最佳实践
category: 学习层
tags: [Docker, 容器化, 部署]
difficulty: 进阶
reading_time: 12 分钟
updated: 2026-07-21
---

# 容器化部署

## 核心原则

容器化 = 环境一致 + 快速部署 + 易于扩展

## Docker 基础

### Dockerfile 最佳实践

```dockerfile
# 使用官方镜像
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 复制依赖文件
COPY requirements.txt .

# 安装依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制代码
COPY . .

# 暴露端口
EXPOSE 8000

# 运行命令
CMD ["python", "app.py"]
```

### 多阶段构建

```dockerfile
# 构建阶段
FROM python:3.11 as builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --user -r requirements.txt

# 运行阶段
FROM python:3.11-slim
WORKDIR /app
COPY --from=builder /root/.local /root/.local
COPY . .
ENV PATH=/root/.local/bin:$PATH
CMD ["python", "app.py"]
```

## Docker Compose

### 多服务配置

```yaml
version: '3.8'

services:
  web:
    build: .
    ports:
      - "8000:8000"
    depends_on:
      - db
      - redis
    environment:
      - DATABASE_URL=postgresql://db:5432/mydb

  db:
    image: postgres:15
    environment:
      - POSTGRES_DB=mydb
      - POSTGRES_PASSWORD=secret
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine

volumes:
  postgres_data:
```

## 部署最佳实践

### 1. 镜像优化

**原则:**
- 使用小镜像
- 减少层数
- 清理缓存

**优化:**
```dockerfile
# 不推荐
FROM python:3.11
RUN pip install flask
RUN pip install sqlalchemy

# 推荐
FROM python:3.11-slim
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
```

### 2. 安全配置

**原则:**
- 非 root 用户
- 只读文件系统
- 最小权限

**配置:**
```dockerfile
# 创建非 root 用户
RUN useradd -m appuser
USER appuser

# 只读文件系统
docker run --read-only ...
```

### 3. 健康检查

```dockerfile
HEALTHCHECK --interval=30s --timeout=3s \
  CMD curl -f http://localhost:8000/health || exit 1
```

## Kubernetes 部署

### 基本配置

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp
spec:
  replicas: 3
  selector:
    matchLabels:
      app: myapp
  template:
    metadata:
      labels:
        app: myapp
    spec:
      containers:
      - name: myapp
        image: myapp:latest
        ports:
        - containerPort: 8000
        resources:
          limits:
            memory: "256Mi"
            cpu: "500m"
```

## 监控和日志

### 日志收集

```yaml
# Docker 日志配置
logging:
  driver: "json-file"
  options:
    max-size: "10m"
    max-file: "3"
```

### 监控集成

```yaml
# Prometheus 监控
- job_name: 'myapp'
  static_configs:
    - targets: ['localhost:8000']
```

## 常见问题

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| 镜像太大 | 未优化 | 多阶段构建 |
| 启动慢 | 依赖多 | 优化依赖 |
| 内存泄漏 | 未释放 | 资源限制 |

## AI 辅助部署

```markdown
请帮我优化 Docker 部署:

1. 分析当前配置
2. 识别优化点
3. 建议改进方案
4. 生成配置文件
```

## 案例: 容器化部署

### 背景
- 项目: Python Web 应用
- 目标: 容器化部署

### 配置
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["gunicorn", "app:app", "-b", "0.0.0.0:8000"]
```

### 结果
- 镜像大小: 150MB
- 启动时间: 5 秒
- 部署时间: 1 分钟

---

*最后更新: 2026-07-21*
