# Spring 框架规则

> 适用于 Spring 框架的 AI Agent 开发

---

## 框架特性

- IoC/DI 容器
- AOP 代理
- Spring Boot 自动配置
- 声明式事务

## 专用规则 (11 条)

参考 `rules.d/anti_patterns.yml`。

## AI 指导

- 遵循框架约定
- 使用框架内置安全机制
- 保持分层架构

*验证: `python tools/scripts/validate_language_rules.py --lang python --framework spring`*
