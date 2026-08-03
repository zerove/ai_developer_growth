---
title: ADR-009: CI/CD 流水线优化与安全强化
description: ADR-009: CI/CD 流水线优化与安全强化 - 技术文档
category: 治理层
tags: ['ADR', '009', 'ci', 'cd', 'security', 'optimization']
difficulty: 进阶
reading_time: 15 分钟
updated: 2026-08-03
---

# ADR-009: CI/CD 流水线优化与安全强化

## 状态
已通过

## 日期
2026-08-03

## 上下文

项目达到所有质量门禁绿灯（ruff 0、mypy strict 0、ADG error 0、pytest 2509 通过）。需要进一步优化 CI/CD：
- 依赖版本固定与自动更新
- SBOM 生成与许可证扫描
- 发布自动化
- 测试并行化与缓存策略
- 安全扫描强制化与 Secret 扫描

## 决策

分四阶段实施 17 个优化任务：

### 第一阶段：依赖与合规（已完成）

1. **opt-1-1 依赖版本固定**：`uv lock --upgrade` + `uv export --extra dev --extra tools` 生成带哈希的 `requirements-lock.txt`
2. **opt-1-2 Dependabot 自动更新**：每周一 09:00 CN，依赖分组（dev-dependencies、security），补丁版本自动合并
3. **opt-1-3 SBOM 生成**：`cyclonedx-bom` 生成 CycloneDX JSON，30 天保留
4. **opt-1-4 许可证扫描**：`pip-licenses` JSON + 纯文本，阻断 GPL-3.0/AGPL-3.0/SSPL-1.0/BSL-1.0/ELv2

### 第二阶段：发布与测试优化（已完成）

5. **opt-2-1 发布自动化**：标签触发，预发布验证（ruff/mypy/测试/ADG/覆盖率/版本/CHANGELOG），`pypa/gh-action-pypi-publish`，GitHub Release 自动提取 changelog，latest-release 别名
6. **opt-2-2 测试并行矩阵**：Python 3.11/3.12/3.13，新增 `test-sharded`（4 分片 `pytest-split --group-by=duration`），`combine-coverage` 合并产物
7. **opt-2-3 分层缓存策略**：所有作业使用 `hashFiles(pyproject.toml, uv.lock, ruff.toml, mkdocs.yml)` 分层缓存键

### 第三阶段：安全强化（已完成）

8. **opt-3-1 安全扫描缓存**：`security` 作业添加 pip 缓存
9. **opt-3-2 Secret 扫描**：新增 `secret-scan` 作业，TruffleHog 扫描最近 10 次提交，JSON 结果上传

### 第四阶段：文档与示例（进行中）

10. **opt-4-1 ADR 状态审查同步**（本 ADR）
11. **opt-4-2 API 文档自动生成**（计划中）
12. **opt-5-1 示例项目独立 CI**（计划中）
13. **opt-5-2 示例测试覆盖率强制**（计划中）
14. **opt-6-1 根目录预提交钩子**（计划中）
15. **opt-6-2 Justfile 统一命令**（计划中）
16. **opt-6-3 开发容器配置**（计划中）
17. **opt-7-1 社区模板完善**（计划中）

## 影响

### 正面

- 依赖安全性提升：自动更新 + 许可证阻断 + SBOM 审计
- 发布流程零人工干预：标签推送即发布
- CI 耗时优化：分片测试 + 分层缓存预期减少 40%+ 耗时
- Secret 泄露风险降低：TruffleHog 预提交 + CI 双重防线
- 治理文档同步：ADR 索引自动维护

### 负面

- CI 作业数量增加（从 ~15 个增至 ~20 个），并发资源消耗上升
- TruffleHog 首次运行需下载二进制，增加 ~30 秒冷启动
- Dependabot PR 可能产生噪音，需定期清理

## 指标

| 指标 | 优化前 | 优化后（预期） |
|--------|--------|-------|
| CI 总耗时 | ~12 分钟 | ~7 分钟 |
| 依赖漏洞响应 | 手动 | 自动（周度） |
| 发布操作 | 手动 15 分钟 | 自动 3 分钟 |
| Secret 泄露检测 | 无 | 双重防线 |
| 许可证合规 | 无 | 自动阻断 |

## 相关 ADR

- ADR-003: 四道质量门禁系统设计
- ADR-008: 生产级稳健工作流与防御性接口设计