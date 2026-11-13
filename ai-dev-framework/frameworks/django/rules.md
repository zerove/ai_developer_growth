# Django 框架规则

> 适用于 Django 框架的 AI Agent 开发

---

## 框架特性

- MTV 架构
- ORM 层
- 中间件链
- REST framework 集成

## 专用规则 (12 条)

参考 `rules.d/anti_patterns.yml`。

## AI 指导

- 遵循框架约定
- 使用框架内置安全机制
- 保持分层架构

*验证: `python -m tools.scripts.validate_language_rules --lang python --framework django`*
