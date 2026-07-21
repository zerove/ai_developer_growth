# 项目上下文

## 项目状态

- **阶段**: M3 社区启动完成 (2026-07-21)
- **成熟度**: 95/100 (优秀) - 详见 AUDIT_REPORT.md
- **核心资产**: 知识库 (37 篇核心文档) + 治理框架 (36 规范) + 11 真实案例 + 5 代码示例

## 关键决策

| 日期 | 决策 | 背景 | 影响 |
|------|------|------|------|
| 2026-07-21 | 质量提升冲刺 | 测试覆盖率 43%、无 CI、缺 LICENSE | 覆盖率 84%、CI/CD 建立、LICENSE 添加 |
| 2026-07-19 | 知识优先重构 | 从工具优先转为文档优先 | 核心价值在方法论文档，代码为验证手段 |
| 2026-07-17 | 治理框架通用化 | 提取 ai-dev-framework 独立复用 | 任何项目可直接复制 GOVERNANCE.md 使用 |
| 2026-07-15 | 双重框架并存 | .ai-framework/ (根目录) + ai-dev-framework/ (独立) | 维护成本双倍，需合并 |
| 2026-07-21 | 双重框架合并完成 | 删除 .ai-framework/，统一使用 ai-dev-framework/ | 消除维护冗余，单一源头 |
| 2026-07-14 | 11 案例达标 | 超过 10+ 目标 | M2 里程碑完成 |
| 2026-07-19 | 安全漏洞修复 | 3 个 Critical 漏洞 (SEC-01/02/03) | 已全部修复，详见 AUDIT_REPORT.md |

## 已完成模块

- ✅ 核心方法论文档 (认知层 7 + 学习层 3 + 效率层 18 + 工具层 2 = 30 篇)
- ✅ 治理框架 (13 语言 + 11 框架 + 12 领域 = 36 规范)
- ✅ 11 个真实案例研究 (效率提升 4x-12x)
- ✅ 5 个代码示例 (2 个参考实现 + 3 个教学示例)
- ✅ 4 条 ADR (Git 解析、知识优先重构、质量门禁、Agent 协作)
- ✅ CI/CD 工作流 (统一 ci.yml: pre-commit, lint, type-check, test, link-audit, case-study-validation, governance-audit, security-scan, docs-check)
- ✅ MCP 集成 (ai-context-sync 作为 MCP Server)
- ✅ 测试覆盖率 84% (152 个测试，目标 ≥70%)
- ✅ LICENSE 文件 (MIT)
- ✅ jcode 集成 (4 个 Agent Skills + Swarm 配置)

## 进行中

- 🔄 M4 规划 - AI 导航和个性化路径设计

## 下一步计划 (优先级顺序)

### P0 - 已完成 ✅
1. **CI/CD 整合** - 统一 ci.yml，修复分支触发，添加 pre-commit 和安全扫描
2. **Makefile 增强** - 添加 install/format/type-check/test-cov/security/clean 等目标
3. **开发依赖分离** - 创建 requirements-dev.txt，分离开发和生产依赖
4. **社区基础设施** - Issue 模板、PR 模板、标签配置、贡献指南

### P1 - 下周完成
9. **收集首批案例** - 邀请早期用户提交案例
10. **发布公告** - 在社交媒体/社区宣布项目上线
11. **M4 规划** - AI 导航和个性化路径设计

### P2 - 本月完成
12. **升级示例为生产级** - 完整测试、文档、部署配置
13. **能力等级定义** - 定义 AI 时代开发者的能力模型

## 阻塞项

| 阻塞项 | 影响 | 解决方案 | 状态 |
|--------|------|----------|------|
| 双重治理框架冗余 | 维护成本双倍，易不一致 | 合并为单一源头，保留 ai-dev-framework/ 作为分发包 | ✅ 已完成 |
| 核心 Agent 定义缺失 | 无法自动化治理流程 | 基于模板创建 4 个 agent 定义文件 | ✅ 已完成 (4 个定义在 agents/ 目录) |
| 文档链接不一致 | 用户导航困惑，CI 可检测 | 统一链接格式，添加 link_auditor CI 检查 | ✅ 已完成 (18 个断链修复) |
| 缺少 conftest.py | 测试 fixture 重复，pytest 警告 | 在根目录和 ai-context-sync 添加 conftest.py | ✅ 已完成 |
| 无远程仓库 | 无法协作、CI 无法运行 | 配置 GitHub/GitLab remote | ✅ 已完成 (https://github.com/zerove/ai_developer_growth) |

## 关键指标

| 指标 | 当前值 | 目标值 | 趋势 |
|------|--------|--------|------|
| 核心文档数 | 37 | 40+ | 📈 |
| 真实案例数 | 11 | 15+ | 📈 |
| 测试覆盖率 | 84% (152 tests) | ≥70% | ✅ 达标 |
| 代码质量 | ruff 0 errors | 0 errors | ✅ |
| 安全评分 | 85/100 | 90/100 | 📈 |
| 文档完整性 | 85/100 | 95/100 | 📈 |
| CI/CD | 8 jobs | 全覆盖 | ✅ |

## 技术债务 (需偿还)

- [x] 测试覆盖率不均 (TEST-01) - 43% → 84% ✅
- [x] 缺少 conftest.py (TEST-02) - 已创建共享 fixtures ✅
- [x] 双重 requirements.txt (DEP-03) - 已合并 ✅
- [x] 28 个宽泛 `except Exception` 捕获 (CODE-02) - 已替换为具体异常 ✅
- [x] 3 处重复文件块解析逻辑 (CODE-03) - 已提取为 `_apply_file_blocks` ✅
- [x] 1 个死代码方法 `_build_test_prompt()` (CODE-04) - 已删除 ✅
- [x] 配置序列化手动枚举字段 (CODE-05) - 已使用 `dataclasses.asdict()` ✅
- [x] 4 处冗余模块内导入 (CODE-06) - 已清理 ✅
- [x] LLM JSON 解析脆弱 (CODE-09) - 已增强健壮性 ✅
- [x] `sys.path` 操作导入 (CODE-10) - 已优化 ✅

---

*最后更新: 2026-07-21 05:34*