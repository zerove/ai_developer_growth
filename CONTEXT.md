# 项目上下文

## 项目状态

- **阶段**: Phase 9 进行中 - AI 开发流程规范补全 (2026-07-22)
- **成熟度**: 98/100 (优秀) - 详见 AUDIT_REPORT.md
- **核心资产**: 知识库 (218 篇文档) + 治理框架 (41 规范) + 35 真实案例 + 7 代码示例 (含向量搜索)

## 关键决策

| 日期 | 决策 | 背景 | 影响 |
|------|------|------|------|
| 2026-07-22 | AI 开发流程规范补全 | 缺失 15 个标准文档 | 新增: 5个P0 + 5个P1 + 5个P2 = 15个标准文档 |
| 2026-07-19 | 知识优先重构 | 从工具优先转为文档优先 | 核心价值在方法论文档，代码为验证手段 |
| 2026-07-17 | 治理框架通用化 | 提取 ai-dev-framework 独立复用 | 任何项目可直接复制 GOVERNANCE.md 使用 |
| 2026-07-15 | 双重框架并存 | .ai-framework/ (根目录) + ai-dev-framework/ (独立) | 维护成本双倍，需合并 |
| 2026-07-21 | 社区策略调整 | 不开放 PR，只接受 Issue 反馈 | 降低维护成本，专注内容质量 |
| 2026-07-14 | 11 案例达标 | 超过 10+ 目标 | M2 里程碑完成 |
| 2026-07-19 | 安全漏洞修复 | 3 个 Critical 漏洞 (SEC-01/02/03) | 已全部修复，详见 AUDIT_REPORT.md |

## 已完成模块

- ✅ AI 开发流程规范补全 (15 个标准文档)
  - P0 (5): 代码生成质量、模型选型、SDLC、代码审查清单、非确定性测试
  - P1 (5): 幻觉检测缓解、代码归属许可、开发环境配置、上下文窗口管理、性能基准
  - P2 (5): 调试专项、代码版本控制、部署运维、开发者培训、工具链标准
- ✅ 核心方法论文档 (203 篇，超额完成 200 篇目标)
- ✅ 治理框架 (18 语言 + 11 框架 + 12 领域 = 41 规范)
- ✅ 35 个真实案例研究 (效率提升 3x-27x)
- ✅ 7 个代码示例
  - ai-context-sync: 上下文同步 (MCP Server)
  - ai-navigation: AI 导航系统 (RAG + 个性化推荐)
  - multi-agent-orch: 多 Agent 编排
  - self-correction-loop: 自我修正循环
  - ai-task-prioritizer: 任务优先级
  - prompt-optimizer: Prompt 优化
  - capability-radar: 能力雷达图
- ✅ 7 条 ADR (Git 解析、知识优先重构、质量门禁、Agent 协作、AI 导航、知识产品化、M4 设计)
- ✅ CI/CD 工作流 (统一 ci.yml: pre-commit, lint, type-check, test, link-audit, case-study-validation, governance-audit, security-scan, docs-check)
- ✅ MCP 集成 (ai-context-sync 作为 MCP Server)
- ✅ 增强检索系统
  - BM25 评分算法
  - 同义词扩展 (中英文技术术语)
  - 协同过滤推荐
- ✅ Phase 4 向量搜索引擎 + RAG 优化 + 对话界面 + 个性化导师
  - sentence-transformers + cosine similarity 语义搜索
  - BM25 + 向量混合搜索 (Reciprocal Rank Fusion)
  - chat_interface.py: CLI 对话式问答系统
  - personalized_mentor.py: 五维能力评估 + 个性化学习计划
  - 18 个向量/混合搜索测试 + 11 个对话测试 + 10 个导师测试
- ✅ 7 个示例项目全部 README.md
- ✅ 测试覆盖率 84% (175 根目录 + 56 ai-navigation + 25 web + 7 slack + 其他示例，目标 ≥70%)
- ✅ LICENSE 文件 (MIT)
- ✅ 通用治理框架 (ai-dev-framework)
  - project_config.py: 参数化配置系统
  - hook_system.py: 通用钩子配置
  - jcode_init.py: 项目初始化命令
  - agent-templates.md: Agent 定义模板
- ✅ 社区基础设施 (Issue 模板、PR 模板、标签、贡献指南、安全政策)

## 已完成全部计划

- ✅ 内容完善 - 203 篇文档 (目标 200 篇，已超额完成)
- ✅ Phase 1-4 全部完成
- ✅ GitHub Pages 部署上线
- ✅ 7 个示例全部有 README
- ✅ 向量搜索引擎集成

## 下一步计划 (长期)

### P1 - 对话界面
1. 基于向量搜索的对话式问答
2. 个性化导师功能

### P2 - 社区增长
1. 活跃贡献者招募
2. 贡献者激励计划

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
| 核心文档数 | 203 | 200 | ✅ 超额完成 |
| 真实案例数 | 35 | 35 | ✅ 达标 |
| 代码示例 | 7 (全有 README) | 7 | ✅ 达标 |
| 向量搜索 | vector_search + hybrid_search | 完成 | ✅ |
| 示例测试 | 175 + 35 + 45 = 255 | ≥200 | ✅ 超额 |
| ADR | 7 | 6+ | ✅ 达标 |
| 测试覆盖率 | 84% | ≥70% | ✅ 达标 |
| 代码质量 | ruff 0 errors | 0 errors | ✅ |
| 安全评分 | 90/100 | 90/100 | ✅ 达标 |
| 文档完整性 | 92/100 | 95/100 | 📈 |
| CI/CD | 9 jobs | 全覆盖 | ✅ |

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

*最后更新: 2026-07-21 18:45*