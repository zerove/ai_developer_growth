---
title: 治理框架快速参考卡
description: ## 核心原则
category: 治理层
tags: ['AI', 'API', 'REST', 'Kubernetes', 'Python']
difficulty: 初级
reading_time: 10 分钟
updated: 2026-07-21
---

# 治理框架快速参考卡

## 核心原则

| 原则 | 描述 | 违反后果 |
|------|------|----------|
| **具体性** | 指令必须包含具体工具名、文件路径 | 无法验证 |
| **可验证性** | 执行后必须有明确成功/失败判定 | 无法审计 |
| **原子性** | 一条指令只做一件事 | 难以追踪 |
| **最小权限** | Agent 只能访问必要资源 | 安全风险 |

---

## 开发流程 (5 步)

```
① 需求分析 → ② Prompt 设计 → ③ 实现编码 → ④ 自动化审计 → ⑤ 资产更新
```

---

## 质量门禁 (4 道)

| Gate | 检查内容 | 执行方式 |
|------|----------|----------|
| Gate 1 | Prompt 设计审查 | 人工/对照模板 |
| Gate 2 | 实现编码审查 | grep + LSP |
| Gate 3 | 自动化审计 | ai_guard + ai_audit |
| Gate 4 | 资产更新审查 | 人工检查 |

---

## 语言选择速查

| 语言 | 文件 | 关键点 |
|------|------|--------|
| Python | `languages/python.md` | ruff + mypy + 类型注解 |
| Rust | `languages/rust.md` | 无 unwrap + Result + lifetime |
| TypeScript | `languages/typescript.md` | strict + ESLint + 接口优先 |
| Go | `languages/go.md` | errcheck + golangci-lint |
| Java | `languages/java.md` | Checkstyle + SpotBugs |
| C# | `languages/csharp.md` | StyleCop + .editorconfig |
| Kotlin | `languages/kotlin.md` | ktlint + detekt |
| PHP | `languages/php.md` | PHPStan + Psalm |
| Ruby | `languages/ruby.md` | RuboCop + Steep |
| C/C++ | `languages/cpp.md` | clang-tidy + cppcheck |
| Swift | `languages/swift.md` | SwiftLint + SwiftFormat |
| Scala | `languages/scala.md` | Scalafmt + WartRemover |
| Elixir | `languages/elixir.md` | Credo + Dialyxir |

---

## 框架选择速查

| 框架 | 文件 | 关键点 |
|------|------|--------|
| React | `frameworks/react.md` | 函数组件 + Hooks 规则 |
| Vue | `frameworks/vue.md` | Composition API + TypeScript |
| Angular | `frameworks/angular.md` | 依赖注入 + RxJS |
| Svelte | `frameworks/svelte.md` | 响应式声明 + Stores |
| Next.js | `frameworks/nextjs.md` | App Router + Server Components |
| NestJS | `frameworks/nestjs.md` | 模块化 + 装饰器 |
| Express | `frameworks/express.md` | 中间件 + 错误处理 |
| Flask | `frameworks/flask.md` | 蓝图 + 应用工厂 |
| Django | `frameworks/django.md` | MTV + Admin + ORM |
| FastAPI | `frameworks/fastapi.md` | 依赖注入 + Pydantic |
| Spring Boot | `frameworks/springboot.md` | 自动配置 + Starter |

---

## 领域速查

| 领域 | 文件 | 关键点 |
|------|------|--------|
| Docker | `devops/docker.md` | 多阶段构建 + 非 root |
| Kubernetes | `devops/kubernetes.md` | Deployment + Service + HPA |
| CI/CD | `devops/cicd.md` | Pipeline as Code |
| SQL | `database/sql.md` | 索引优化 + 事务隔离 |
| NoSQL | `database/nosql.md` | 一致性模型 + 分片策略 |
| REST | `api/rest.md` | 资源命名 + 状态码 |
| GraphQL | `api/graphql.md` | Schema 设计 + N+1 问题 |
| gRPC | `api/grpc.md` | Proto 设计 + 流式通信 |
| 认证 | `security/authentication.md` | JWT + OAuth2 + RBAC |
| OWASP | `security/owasp.md` | Top 10 防护清单 |
| 测试 | `testing/strategy.md` | 测试金字塔 + Mock 策略 |
| Git | `testing/git-workflow.md` | 分支策略 + 提交规范 |

---

## 禁止行为清单

### 通用禁止

- ❌ `unwrap()` / `expect()` 在生产代码
- ❌ `as any` / `@ts-ignore` / `@ts-expect-error`
- ❌ 空 catch 块 `catch(e) {}`
- ❌ 硬编码密钥/凭证
- ❌ 跳过质量门禁
- ❌ 未更新文档完成开发

### 语言特定禁止

| 语言 | 禁止 |
|------|------|
| Python | 裸 except、未类型注解函数 |
| Rust | unwrap、panic!、未处理 Option |
| TypeScript | any 类型、非空断言滥用 |
| Go | panic、未检查 error |
| Java | 空指针、未关闭资源 |

---

## 快速命令

```bash
# 复制治理标准到新项目
cp GOVERNANCE.md /path/to/project/

# 安装语言特定规范
cp docs/governance/languages/python.md /path/to/project/.ai-governance/

# 运行审计 (需要 ai_guard/ai_audit)
ai_guard --config .ai-governance/
ai_audit --report

# 查看可视化地图
cat docs/governance/MAP.md
```

---

*本参考卡随项目演进持续更新。最后更新: 2026-07-17*
