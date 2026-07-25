# ADG Governance - 后续开发计划

## 当前状态 (v1.0)

| 组件 | 状态 | 测试覆盖 |
|------|------|----------|
| CLI (5 commands) | ✅ 完成 | 117 tests |
| 22 语言规则 | ✅ 完成 | ✅ |
| 9 框架规则 | ✅ 9/9 有 YAML | 需补充 |
| 全局 Git Hook | ✅ 零配置 | ✅ |
| Jcode Skill | ✅ 完成 | ✅ |
| CI 集成 | ✅ GitHub Actions | ✅ |
| 质量报告 | ✅ 完成 | ✅ |

---

## P0 - 高优先级 (1-2 周)

### 1. 补充框架规则 YAML
**目标**: 将框架规则从 5/9 扩展到 9/9

| 框架 | 当前状态 | 工作量 |
|------|----------|--------|
| actix | 仅 markdown | 中 |
| express | 仅 markdown |
| nextjs | 仅 markdown | 中 |
| spring-boot | 仅 markdown | 中 |

**任务**:
- [x] 解析 markdown 规则转换为 YAML
- [x] 添加框架特定检测逻辑
- [x] 添加测试用例
- [x] 添加 naming/thresholds/tooling sections

### 2. Auto-fix 修复常见问题

```bash
adg check . --fix  # 自动修复可修复的问题
```

**支持的修复**:
- `py-bare-except` → `except Exception:`
- `js-==null` → `=== null`
- `common-unused-import` → 删除未使用导入
- `rust-unwrap` → 替换为 `expect("message")`
- `ts-any` → `unknown`

**任务**:
- [x] 设计 fix_hint 结构化格式
- [x] 实现 Python 修复器 (最高优先)
- [x] 实现 JavaScript/TypeScript 修复器
- [x] 实现 Rust 修复器

### 3. 增强 CI 集成
**目标**: 支持更多 CI/CD 平台

```yaml
# GitLab CI
adg-governance:
  script:
    - adg check . --severity error --json > adg-report.json
  artifacts:
    reports:
      codequality: adg-report.json

# Azure Pipelines
# Jenkins
# CircleCI
```

**任务**:
- [x] GitLab CI 模板
- [x] Azure Pipelines 模板
- [x] Jenkins Pipeline 模板
- [x] 统一 JSON 输出格式 (兼容 codeclimate)

---

## P1 - 中优先级 (2-4 周)

### 4. 自定义规则支持
**目标**: 允许用户创建项目特定规则

```yaml
# .adg/rules.yml
language: python
custom_rules:
  - id: my-no-print
    name: No print statements
    severity: warning
    pattern: 'print\('
    message: Use logging instead of print
    fix_hint: 'import logging; logging.info(...)'
```

**任务**:
- [x] 支持 `.adg/rules.yml` 项目配置
- [x] 支持 `~/.config/adg/rules.yml` 用户全局配置
- [x] 规则继承和覆盖机制
- [x] 文档和示例

### 5. 并行检查
**目标**: 大型代码库性能优化

**当前**: 串行检查 1000+ 文件
**目标**: 并行检查，减少 50%+ 时间

**任务**:
- [x] 实现多进程检查器
- [x] 添加 `--jobs N` 参数
- [x] 性能基准测试

### 6. Pre-push Hook
**目标**: 推送前质量门禁

```bash
adg install-hooks --pre-push  # 安装 pre-push hook
```

**任务**:
- [x] 实现 pre-push hook 脚本
- [x] 添加 `install-hooks --pre-push`
- [x] 支持增量检查 (仅检查未推送的提交)

---

## P2 - 低优先级 (1-2 月)

### 7. GitHub/GitLab 集成
**目标**: PR/MR 自动评论质量报告

```bash
adg github-pr-comment  # 在 PR 中评论质量报告
```

**功能**:
- 自动评论 PR 质量变化
- 阻止合并如果有 error
- 历史趋势图

**任务**:
- [x] GitHub Actions 工作流
- [x] GitLab MR 集成
- [x] 质量趋势追踪

### 8. 质量仪表板
**目标**: 可视化质量报告

```bash
adg dashboard  # 启动本地 Web 仪表板
```

**功能**:
- 质量趋势图
- 按文件/目录分组
- 历史对比
- 导出 PDF 报告

**技术栈**:
- 后端: Python + FastAPI
- 前端: React + Recharts
- 存储: SQLite

### 9. 语言扩展
**目标**: 支持更多语言

**待添加**:
- Kotlin (Android)
- Swift (iOS)
- TypeScript (增强)
- Python (更多规则)
- Rust (更多规则)

---

## P3 - 实验性功能

### 10. AI 驱动的规则生成
**目标**: 从代码库自动生成规则

```bash
adg learn ./my-project  # 分析项目生成规则
```

**功能**:
- 分析项目代码模式
- 识别常见反模式
- 生成自定义规则建议

### 11. LSP 集成
**目标**: IDE 实时反馈

- VS Code 扩展
- Neovim/LSP 集成
- IntelliJ 插件

---

## 技术债务

### 已清理
- [x] `_simple_yaml_parse` 替换为完整 YAML 解析器 (PyYAML)
- [x] 添加类型注解到所有函数 (from __future__ import annotations)
- [x] 提取常量到配置文件 (constants.py)
- [x] 添加文档字符串到所有公共函数

### 性能优化
- [x] 缓存规则解析结果 (disk + memory cache)
- [x] 增量检查 (仅检查修改的文件)
- [x] 正则编译时间 (regex_cache.py)

---

## 里程碑规划

| 版本 | 时间 | 主要特性 |
|------|------|----------|
| v1.1 | 2 周 | 框架规则补全, Auto-fix, CI 集成, 自定义规则, 并行检查, Pre-push hook | ✅ 已完成 |
| v1.2 | 1 月 | PR 集成, Dashboard, 语言扩展 | 部分完成 |
| v1.3 | 2 月 | GitHub/GitLab 集成, 质量仪表板 | 待完成 |
| v2.0 | 3 月 | LSP 集成, AI 规则生成 | 待完成 |

---

## 贡献指南

欢迎贡献！请查看:
- [CONTRIBUTING.md](./CONTRIBUTING.md)
- [Good First Issues](https://github.com/your-repo/adg/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22)

---

*最后更新: 2026-07-24*
