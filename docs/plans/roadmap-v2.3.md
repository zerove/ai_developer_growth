# 功能路线图 v2.3+ (2026 Q3-Q4)

> 基于当前 v2.2.0 稳定版的下一阶段规划。
> 历史路线图见 `ROADMAP.md`（v1.0-v2.0）。

---

## 当前基线

```
语言规则:  ✅ 26语言 × 699条 + universal × 9条
框架规则:  ✅ 9框架 × 10-17条 + check.sh全量
通用规则:  ✅ universal.yml 适用于任意语言
LLM 生成:  📋 架构文档就绪，待编码
jcode 集成: ✅ adg CLI / init-governance / mode-switch / 多路径搜索
CI/CD:      ✅ 6工作流覆盖全部事件周期
测试:       ✅ 2474 passed, 87.52% 覆盖率
```

---

## P0 — 核心能力补齐（1-2 周）

### 1. LLM 规则生成器

**现状**: `docs/architecture/llm-rule-generation.md` 有 Prompt 模板，无可执行代码。

**目标**: 实现 `tools/scripts/rules_engine/llm_rules_generator.py`，接收语言名 + 文件样本，调用 LLM API 返回 YAML 规则，缓存到本地。

**工作流**:
```
jcode 遇到 .mojo 文件
  → rule_loader 返回 27 条通用规则
  → llm_rules_generator 异步调用 LLM
  → 生成 5-8 条 Mojo 专属规则
  → 缓存到 ~/.jcode/governance/languages/mojo/
  → 下次检查自动加载 27+8=35 条规则
```

| 模块 | 预估 |
|------|------|
| LLM 客户端（OpenAI/Anthropic 兼容） | 2h |
| 规则解析与 YAML 缓存 | 1h |
| `rule_loader` 集成（自动发现缓存） | 1h |
| 测试（mock LLM） | 1h |
| **总计** | **5h** |

**验收**: `.mojo` 文件运行 `adg check` 自动触发 LLM 生成并缓存规则。

---

### 2. Dashboard 2.0

**现状**: 基础 FastAPI + SQLite 存在，功能有限（`tools/scripts/rules_engine/dashboard.py`）。

**目标**:

| 功能 | 优先级 | 预估 |
|------|--------|------|
| 趋势折线图（ECharts/Chart.js） | P0 | 2h |
| 按语言/框架拆分视图 | P0 | 1h |
| 历史对比（当前 vs 上周） | P1 | 1h |
| CI 失败关联 | P2 | 2h |

**验收**: 打开 `adg dashboard` 看到 7 天质量趋势图 + 按语言分类。

---

## P1 — 体验增强（3-4 周）

### 3. 自动修复引擎跨语言

**现状**: `auto_fix.py` 支持 5 语言，`ast_fixer.py` 仅 Python。

| 语言 | 当前修复数 | 目标 |
|------|-----------|------|
| Python | 7 | 10+ |
| TypeScript | 3 | 8+ |
| Go | 0 | 5+ |
| Rust | 2 | 5+ |

### 4. VS Code / Zed 扩展同步

**现状**: `extensions/` 下 4 个扩展，未与当前规则引擎保持同步。

| 扩展 | 平台 | 当前 | 目标 |
|------|------|------|------|
| `vscode-adg` | VS Code | TS 扩展 | 实时诊断 + 自动修复 |
| `zed-adg` | Zed | Rust | LSP 协议 |
| `ai-language-rules` | Zed | Python LSP | 兼容 |

---

## P2 — 生态建设（月度）

### 5. 社区案例激活

**现状**: 35 案例全内部，0 社区。`TEMPLATE-community.md` + Issue 模板就绪。

| 措施 | 状态 |
|------|------|
| Issue 模板 | ✅ 已优化 |
| 贡献者排行榜 | ✅ CLI 命令 |
| 奖励机制文档 | 📋 已起草 |
| 案例审核自动化 | ❌ 待实现 |

### 6. 知识库-规则联动

**现状**: 245 篇文档与 756 条规则各自独立。

**目标**: 规则触发时自动推荐相关文档，文档中自动标注关联规则。

---

## 发布版本规划

| 版本 | 时间 | 内容 |
|------|------|------|
| **v2.3.0** | 2026-08 | LLM 规则生成器 + Dashboard 2.0 |
| **v2.4.0** | 2026-09 | 自动修复跨语言 + 扩展更新 |
| **v2.5.0** | 2026-10 | 社区生态 + 知识库联动 |
| **v3.0.0** | 2026-Q4 | Governance API + 多仓库支持 |

---

## 技术债务清理

| 项 | 操作 |
|----|------|
| `test_cov/` 目录 | 删除 |
| `python/` 空目录 | 删除 |
| `.ai-sync-cache/` | 清理 |
| `ai_developer_growth.egg-info/` | gitignore |
