---
title: "v2.1.0 Release Notes"
description: "发布日期: 2026-07-25"
category: 治理层
tags: ['发布日期', '主要新功能', '框架规则完整覆盖', '所有', '个框架现在都有完整的', '配置']
difficulty: 基础
---

# v2.1.0 Release Notes

**发布日期**: 2026-07-25

## 🎉 主要新功能

### P0: 框架规则完整覆盖 (9/9)

所有 9 个框架现在都有完整的 YAML 配置：
- actix, express, nextjs, spring-boot — 新增 naming/thresholds/tooling 部分
- 每个框架包含 8-12 个反模式检测规则

### P0: 自动修复引擎

`adg check . --fix` — 自动修复常见代码问题：

| 语言 | 支持的修复 |
|------|-----------|
| Python | bare-except, eval, print, yaml.load, Optional 语法 |
| JavaScript | eval, var, innerHTML, console.log, debugger |
| TypeScript | any 类型, as any, require() |
| Rust | unwrap(), panic! |
| Java | System.out.println, printStackTrace |

### P0: CI/CD 集成模板

一键集成到主流 CI/CD 平台：
- GitLab CI + MR 自动评论
- Azure Pipelines
- Jenkins Pipeline
- CircleCI
- GitHub Actions PR 质量报告

所有模板生成 CodeClimate 兼容的 JSON 输出。

### P1: 自定义规则

三级规则继承机制：
```
~/.config/adg/rules.yml  (用户全局)
  ↓ 覆盖
.adg/rules.yml           (项目级)
  ↓ 覆盖
.ai-rules/*.yml          (遗留目录)
```

支持 severity_override 覆盖内置规则。

### P1: 并行检查

`--jobs N` 参数支持多进程并行检查：
```bash
adg check . --jobs 4  # 使用 4 个进程
```

### P1: Pre-push Hook

```bash
adg install-hooks --pre-push
```

推送前自动检查未推送提交的代码质量。

### P2: 质量仪表板

```bash
adg dashboard --port 8765
```

FastAPI + SQLite Web 仪表板，包含：
- 质量趋势图 (Chart.js)
- 文件级详情
- REST API (`/api/trend`, `/api/latest`, `/api/record`)
- 暗色主题响应式 UI

### P2: GitHub/GitLab PR 集成

自动在 PR/MR 中发布质量报告评论，推送更新时自动刷新。

### P2: 语言扩展

- Kotlin: 10 个反模式规则 (协程阻塞、空断言、可变数据类等)
- Swift: 10 个反模式规则 (强制解包、retain cycle、force cast 等)

### P3: AI 规则生成

```bash
adg learn ./my-project -o .adg/rules.yml
```

分析代码库，检测 10+ 种模式，生成。

### P3: LSP 服务器

IDE 实时诊断，支持：
- Diagnostics (实时代码质量反馈)
- Hover (规则文档悬停)
- Code Actions (快速修复建议)

## 🔧 技术改进

- `regex_cache.py`: 正则编译缓存，提升检查性能
- `constants.py`: 集中配置常量
- 所有函数添加类型注解
- 所有公共函数添加文档字符串
- 修复 `generate_fixes.py` 导入路径
- 修复 `_run_simple` callable 处理
- Dashboard SQLite 线程安全修复
- 治理检查 `exclude_files` 支持

## 📊 测试

- 新增 62 个测试 (auto_fix, dashboard, ai_rules_generator, pre_push)
- 总测试数: 840+

## 📝 文档

- Dashboard 使用文档
- AI Learn 使用文档
- LSP 集成指南
- CI/CD 模板 README

## 🙏 贡献者

感谢所有贡献者使这个版本成为可能！

---

**升级方式**: `pip install -e .`

**破坏性变更**: 无
