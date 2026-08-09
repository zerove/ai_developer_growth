---
title: Terraform 最佳实践
description: > 基础设施即代码的核心工具，覆盖模块化、状态管理、CI/CD、多环境、安全与治理。
category: 工具层
tags: ['AI', 'REST', 'Kubernetes', '测试', '安全']
difficulty: 基础
reading_time: 10 分钟
updated: 2026-07-21
---

# Terraform 最佳实践

> 基础设施即代码的核心工具，覆盖模块化、状态管理、CI/CD、多环境、安全与治理。

---

## 1. 核心原则

| 原则 | 说明 |
|------|------|
| **模块化优先** | 所有资源封装为模块，根模块只编排 |
| **状态隔离** | 环境/项目/团队级状态文件分离 |
| **只读 Plan** | PR 阶段只跑 `plan`，合并后 `apply` |
| **版本锁定** | Provider 版本、模块版本显式锁定 |
| **零手动操作** | 100% GitOps，禁止手动 `apply` |

---

## 2. 目录结构规范

```
terraform/
├── modules/                    # 可复用模块库
│   ├── network/
│   │   ├── vpc/
│   │   ├── subnet/
│   │   └── security-group/
│   ├── compute/
│   │   ├── eks/
│   │   ├── ec2/
│   │   └── lambda/
│   ├── data/
│   │   ├── rds/
│   │   ├── elasticache/
│   │   └── s3/
│   └── security/
│       ├── iam-role/
│       └── kms-key/
│
├── environments/               # 环境级根模块
│   ├── dev/
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   ├── outputs.tf
│   │   └── terraform.tfvars
│   ├── staging/
│   └── prod/
│
├── globals/                    # 跨环境共享资源
│   ├── dns/
│   ├── cert-manager/
│   └── monitoring/
│
├── providers.tf                # 统一 Provider 配置
├── versions.tf                 # 版本锁定
└── backend.tf                  # 后端配置 (可选，环境级覆盖)
```

---

## 3. 模块设计规范

### 3.1 模块接口标准
```hcl
# modules/network/vpc/variables.tf
variable "name" {
  type        = string
  description = "VPC 名称前缀"
}

variable "cidr_block" {
  type        = string
  description = "VPC CIDR 块"
  validation {
    condition     = can(cidrhost(var.cidr_block, 0))
    error_message = "必须是有效的 CIDR 格式"
  }
}

variable "enable_dns_hostnames" {
  type    = bool
  default = true
}

variable "tags" {
  type    = map(string)
  default = {}
}

# 模块输出标准化
# modules/network/vpc/outputs.tf
output "vpc_id" {
  value       = aws_vpc.main.id
  description = "VPC ID"
}

output "private_subnet_ids" {
  value       = aws_subnet.private[*].id
  description = "私有子网 ID 列表"
}

output "public_subnet_ids" {
  value       = aws_subnet.public[*].id
  description = "公有子网 ID 列表"
}
```

### 3.2 模块调用示例
```hcl
# environments/prod/main.tf
module "vpc" {
  source  = "../../modules/network/vpc"
  version = "v2.1.0"  # Git tag 或本地路径

  name             = "prod"
  cidr_block       = "10.0.0.0/16"
  enable_dns_hostnames = true

  tags = {
    Environment = "prod"
    ManagedBy   = "terraform"
    Owner       = "platform-team"
  }
}
```

---

## 4. 状态管理

### 4.1 后端配置
```hcl
# backend.tf (或 environments/*/backend.tf)
terraform {
  backend "s3" {
    bucket         = "tf-state-prod"
    key            = "prod/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "tf-state-locks"
  }
}
```

### 4.2 状态隔离策略

| 策略 | 适用场景 | 优点 | 缺点 |
|------|----------|------|------|
| **环境隔离** (dev/staging/prod 分桶/分 key) | 标准 | 隔离彻底、权限可控 | 配置重复 |
| **工作区** (`terraform workspace`) | 小团队、简单环境 | 共享配置 | 易误操作、不推荐生产 |
| **Terraform Cloud/Enterprise** | 企业、多团队 | RBAC、Policy、私有 Registry | 成本、厂商锁定 |

**推荐**：环境级 S3 + DynamoDB 锁表，配合 IAM 限制。

### 4.3 状态保护
```hcl
resource "aws_s3_bucket" "tf_state" {
  bucket = "tf-state-prod"
  lifecycle {
    prevent_destroy = true
  }
  server_side_encryption_configuration {
    rule { apply_server_side_encryption_by_default { sse_algorithm = "AES256" } }
  }
  versioning { enabled = true }
}
```

---

## 5. 版本锁定

```hcl
# versions.tf
terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.30"  # 小版本浮动，大版本锁定
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.28"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.12"
    }
  }
}
```

**模块版本**：
```hcl
module "vpc" {
  source  = "git::https://github.com/org/terraform-modules.git//modules/network/vpc?ref=v2.1.0"
  # 或本地相对路径
  # source = "../../modules/network/vpc"
}
```

---

## 6. CI/CD 流水线

### 6.1 GitHub Actions 标准流程
```yaml
# .github/workflows/terraform.yml
name: Terraform

on:
  pull_request:
    paths: ['terraform/**']
  push:
    branches: [main]
    paths: ['terraform/**']

env:
  TF_VERSION: '1.6.6'
  AWS_REGION: 'us-east-1'

jobs:
  fmt:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: hashicorp/setup-terraform@v3
        with: { terraform_version: ${{ env.TF_VERSION }} }
      - run: terraform fmt -check -recursive terraform/

  validate:
    runs-on: ubuntu-latest
    needs: fmt
    steps:
      - uses: actions/checkout@v4
      - uses: hashicorp/setup-terraform@v3
      - run: terraform init -backend=false terraform/
      - run: terraform validate terraform/

  plan:
    runs-on: ubuntu-latest
    needs: validate
    if: github.event_name == 'pull_request'
    steps:
      - uses: actions/checkout@v4
      - uses: hashicorp/setup-terraform@v3
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: ${{ env.AWS_REGION }}
      - run: terraform init terraform/environments/dev
      - run: terraform plan -out=tfplan terraform/environments/dev
      - uses: actions/upload-artifact@v4
        with:
          name: tfplan
          path: tfplan

  apply:
    runs-on: ubuntu-latest
    needs: plan
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'
    environment: production
    steps:
      - uses: actions/checkout@v4
      - uses: hashicorp/setup-terraform@v3
      - uses: aws-actions/configure-aws-credentials@v4
        with: { ... }
      - run: terraform init terraform/environments/prod
      - run: terraform apply -auto-approve terraform/environments/prod
```

### 6.2 Plan 产物评审
```yaml
# PR 评论自动化
- uses: actions/github-script@v7
  with:
    script: |
      const fs = require('fs');
      const plan = fs.readFileSync('tfplan', 'utf8');
      github.rest.issues.createComment({
        issue_number: context.issue.number,
        owner: context.repo.owner,
        repo: context.repo.repo,
        body: '## Terraform Plan\n```\n' + plan + '\n```'
      })
```

---

## 7. 安全与治理

### 7.1 OPA Policy (Checkov / tfsec / OPA)
```rego
# policies/terraform.rego
package terraform

deny[msg] {
  resource := input.resource_changes[_]
  resource.type == "aws_s3_bucket"
  not resource.change.after.versioning.enabled
  msg := sprintf("S3 bucket %s must have versioning enabled", [resource.address])
}

deny[msg] {
  resource := input.resource_changes[_]
  resource.type == "aws_db_instance"
  not resource.change.after.storage_encrypted
  msg := sprintf("RDS %s must be encrypted", [resource.address])
}
```

```yaml
# CI 集成
- name: Checkov Scan
  uses: bridgecrewio/checkov-action@v12
  with:
    directory: terraform/
    framework: terraform
    skip_check: CKV_AWS_21  # 例外
```

### 7.2 变量验证
```hcl
variable "instance_type" {
  type = string
  validation {
    condition     = contains(["t3.micro", "t3.small", "t3.medium"], var.instance_type)
    error_message = "必须使用允许的实例类型"
  }
}

variable "cidr_block" {
  type = string
  validation {
    condition     = can(cidrhost(var.cidr_block, 0)) && cidrnetmask(var.cidr_block) <= 16
    error_message = "CIDR 必须有效且掩码不大于 /16"
  }
}
```

### 7.3 敏感数据处理
```hcl
# 标记敏感输出
output "db_password" {
  value     = aws_db_instance.main.password
  sensitive = true
}

# 环境变量注入 (不要硬编码)
provider "aws" {
  region = var.aws_region
  # credentials 从环境变量 / IRSA / 实例配置文件获取
}
```

---

## 8. 常用模式

### 8.1 条件创建
```hcl
resource "aws_lb" "main" {
  count = var.enable_alb ? 1 : 0
  # ...
}
```

### 8.2 动态块
```hcl
dynamic "ingress" {
  for_each = var.allowed_cidrs
  content {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = [ingress.value]
  }
}
```

### 8.3 依赖显式化
```hcl
resource "aws_db_instance" "main" {
  # ...
  depends_on = [aws_security_group.rds]  # 显式声明，避免竞态
}
```

### 8.4 数据源替代硬编码
```hcl
data "aws_ami" "amazon_linux" {
  most_recent = true
  owners      = ["amazon"]
  filter {
    name   = "name"
    values = ["amzn2-ami-hvm-*-x86_64-gp2"]
  }
}
```

---

## 9. 常见坑清单

| 坑 | 后果 | 预防 |
|----|------|------|
| **无锁并发 apply** | 状态损坏 | DynamoDB 锁表 + `prevent_destroy` |
| **Provider 版本漂移** | 计划不一致 | `versions.tf` 锁定、依赖机器人升级 |
| **模块版本未锁定** | 环境不一致 | `source = "...?ref=v2.1.0"` |
| **敏感值泄露** | 凭据泄露 | `sensitive = true`、环境变量、Secret Manager |
| **手动修改生产资源** | 状态漂移 | 100% GitOps、定期 `plan` 检测漂移 |
| **大资源无分批** | 超时/锁表 | `count`/`for_each` 分批、依赖显式化 |

---

*Terraform 是工具，架构治理才是核心。最后更新: 2026-07-20*
