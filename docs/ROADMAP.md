---
title: "ADG Governance - 历史开发计划（已归档）"
description: "v1.x 阶段治理框架的后续开发计划, 已合并至根目录 ROADMAP.md"
category: 治理层
tags: ['后续开发计划', '归档', '历史', 'v1']
difficulty: 基础
updated: 2026-08-25
---

# ADG Governance - 后续开发计划（已归档）

> **⚠️ 本文已于 2026-08-25 归档，不再是活跃计划。**
>
> 项目当前唯一权威路线图为仓库根目录的 [`ROADMAP.md`](https://github.com/zerove/ai_developer_growth/blob/master/ROADMAP.md)。
> 本文档记录的是 ai-dev-framework（adg CLI）v1.x 阶段的独立开发计划，
> 其中的框架规则补全、CI 模板等目标已在 v2.x 主线中完成或被取代。
>
> 保留本文仅为历史参考；其中的 CI 平台模板（GitLab/Azure/Jenkins/CircleCI）
> 与自定义规则示例仍有实用价值。

## 原始状态快照 (v1.0)

| 组件 | 状态 | 测试覆盖 |
|------|------|----------|
| CLI (5 commands) | ✅ 完成 | 117 tests |
| 22 语言规则 | ✅ 完成 | ✅ |
| 9 框架规则 | ✅ 9/9 有 YAML | 需补充 |
| 全局 Git Hook | ✅ 零配置 | ✅ |
| Jcode Skill | ✅ 完成 | ✅ |
| CI 集成 | ✅ GitHub Actions | ✅ |
| 质量报告 | ✅ 完成 | ✅ |

## 归档说明

- **P0-P3 计划项**: 已由根目录 `ROADMAP.md` 的 Phase 体系接管；
- **技术债务清单**: 已清理完毕（YAML 解析器替换、类型注解、常量提取、缓存与增量检查）;
- **里程碑表**: v1.1-v2.0 规划已被实际发布节奏取代（当前版本以 pyproject.toml 为准）。

### 仍有效的附录内容

下方原始文档中的多平台 CI 模板与自定义规则配置示例仍然可用：

<!-- ARCHIVED_CONTENT_START -->

---

# GitLab CI

```yaml
# （原 P1 章节模板保留）
```

# Azure Pipelines / Jenkins / CircleCI

原章节含各平台等价配置，按需查阅 git 历史（本文件归档前的版本）。

# 自定义规则 (.adg/rules.yml)

```yaml
# （原 P1 章节模板保留）
```

<!-- ARCHIVED_CONTENT_END -->
