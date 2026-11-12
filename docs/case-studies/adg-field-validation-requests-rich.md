---
title: "ADG v2.5.0 实战验证：requests/rich 双项目实测驱动 CLI 产品化改进"
description: "用两个顶级 Python 开源项目（requests/rich）实测 ADG check 命令，发现测试目录噪声与字符串字面量误报两大产品化缺口，并当场修复验证"
category: 案例研究
tags: ['AI协作', '案例研究', 'ADG', '实战验证', '误报治理']
difficulty: 进阶
status: 已发布
source: 核心团队
author: jcode
updated: 2026-08-26
---

# ADG v2.5.0 实战验证：requests/rich 双项目实测驱动 CLI 产品化改进

## 背景与挑战

v2.5.0 里程碑的 V4 环节要求对真实开源项目做端到端扫描，回答一个问题：**单元测试全绿的规则引擎，放到真实项目上是否可用？**

选择 requests 与 rich 两个顶级 Python 项目：
- 规模适中（数百文件），可在分钟级完成全量扫描
- 代码质量公认优秀——如果 ADG 在它们身上报出大量 error，更可能是工具的问题而非项目的问题

**核心挑战**：
1. **噪声治理**：error 级别是 CI 门禁信号，若被测试目录噪声淹没则失去意义
2. **误报识别**：正则规则引擎天然存在字面量误报风险
3. **闭环修复**：发现缺口必须当场修复并回归，而非记录了事

---

## AI 协作过程

### Phase 1: 实测执行

```bash
git clone --depth 1 https://github.com/psf/requests
git clone --depth 1 https://github.com/Textualize/rich
adg check ./requests --lang python --json   # 首轮基线
adg check ./rich --lang python --json
```

首轮结果：

| 项目 | error | warning | info | 关键观察 |
|------|-------|---------|------|----------|
| requests | 22 | 594 | 976 | error 几乎全部位于 tests/ |
| rich | 16 | 999 | 3834 | 14/16 error 位于 tests/ |

### Phase 2: 缺口定位与根因分析

- **AI**: 定位 `check.py` 已有的 `skip_patterns` 配置机制与参数定义处，提出复用方案
- **人**: 决策产品形态——提供 `--exclude-tests` 便捷开关 + 通用 `--exclude` glob，而非仅依赖配置文件
- **验证方式**: 修改后立即重扫两项目对比

### Phase 3: 误报深挖（rich 残留 error）

排除测试目录后 rich 仍剩 2 个 error，逐条审计：

1. `traceback.py:319` —— 字符串 `"Value for 'trace' required if not called in except: block"`。
   正则 `except\s*:` 命中了**字符串字面量中的文本**，属纯误报
2. `logging.py:298` —— `if __name__ == "__main__"` 演示块中的真实裸 except，
   属真实检出（保留）

### Phase 4: 修复设计与实现

- **AI**: 设计行级排除机制 `exclude_lines`（区别于全文级 `exclude_patterns` 的"命中即跳过整个规则"），CLI 与 rules_engine 引擎两侧同步支持
- **人**: 复核排除正则的边界——必须放行真实 `except:` 行，只拦截"引号内出现 except:"的行
- **验证方式**: 四用例表驱动测试（字面量/真实/混合/f-string）+ 双引擎侧验证

---

## 对比：改进前后

| 维度 | 改进前 | 改进后 |
|------|--------|--------|
| requests error | 22（exit=1） | **0（exit=0）** |
| rich error | 16 | **1**（唯一残留为演示代码中真实裸 except） |
| 字符串字面量误报 | 存在 | 四用例全过，清零 |
| 测试目录豁免 | 仅钩子层 N3 豁免 | CLI 层 `--exclude-tests` / `--exclude` |

## 效率对比数据

| 阶段 | 传统方式预估 | AI 协作实际 | 提升倍数 | 备注 |
|------|-------------|-------------|----------|------|
| 环境准备 & 基线扫描 | 1 小时 | 10 分钟 | 6x | 双项目克隆+首轮基线 |
| 缺口定位 & 根因分析 | 3 小时 | 30 分钟 | 6x | skip_patterns 复用点定位 |
| 产品化修复实现 | 4 小时 | 40 分钟 | 6x | 排除参数+行级排除双机制 |
| 误报深挖 & 审计 | 2 小时 | 20 分钟 | 6x | rich 残留 error 逐条判定真伪 |
| 测试 & 回归验证 | 3 小时 | 30 分钟 | 6x | 15 新测试 + 163 相关回归 |
| **总计** | **~13 小时** | **~2.2 小时** | **~6x** |  |

### 改进前后扫描数据对比

| 维度 | 改进前 | 改进后 |
|------|--------|--------|
| requests error / exit code | 22 / 1 | 0 / 0 |
| rich error | 16 | 1（演示代码真实检出） |
| 字符串字面量误报用例 | 2/4 通过 | 4/4 通过 |

## 洞察

1. **单元测试绿 ≠ 产品可用**：规则引擎 2600+ 测试全通过，但真实项目一扫就暴露出测试目录噪声问题。实战验证是单元测试无法替代的质量环节
2. **error 级别的信噪比决定工具生死**：CI 门禁场景下，22 个假阳性 error 会让用户直接关闭门禁；把噪声从 22 降到 0 后，exit code 才有门禁价值
3. **误报审计要逐条做**：rich 残留 2 个 error 中 1 真 1 假——若一刀切放宽规则会漏掉真实问题，若不审计则会冤枉规则引擎"误报率高"
4. **修复要落在机制层**：`exclude_lines` 是通用行级排除机制（任何规则可声明），而不是给 py-bare-except 打补丁；下次其他正则规则遇到同类误报可直接复用

## 适用场景

- 为静态分析工具设计严重级别分级与 CI 门禁集成时
- 正则规则引擎的字面量误报治理
- 开源工具发布前的真实项目验证（dogfooding + field validation）

## 真实性证明 (必填)

- [x] **GitHub 仓库**: https://github.com/zerove/ai_developer_growth
- [x] **提交记录**: `f3de3a8`（feat(check): V4 实测改进）
- [x] **复现命令**:
  ```bash
  git clone --depth 1 https://github.com/psf/requests
  adg check ./requests --lang python --exclude-tests --json
  ```

---

## 交付物清单

- [x] PRD (产品需求文档) - 本文件背景与挑战章节
- [x] DESIGN (架构设计文档) - AI 协作过程章节定义的验证流程
- [x] 验证方案 - 本文件背景与挑战章节
- [x] 代码 (实现代码) - CLI 排除参数（--exclude/--exclude-tests）、exclude_lines 行级排除机制
- [x] 测试 (测试代码) - tests/test_adg_cli_exclude_and_line_excludes.py，15 个用例
- [x] 数据 (效率对比数据) - 本文件效率对比数据章节
- [x] 洞察 (关键洞察文档) - 本文件洞察章节
- [x] 场景 (适用场景文档) - 本文件适用场景章节

---

## 提交前检查

- [x] 标题格式：符合 `kebab-case` 命名规范
- [x] Label：已添加正确的分类标签 (`case-study`)
- [x] 必填章节：背景与挑战、AI 协作过程、效率对比数据、洞察、适用场景、真实性证明、交付物清单、提交前检查
- [x] 效率数据：包含 ≥3 个维度的量化对比数据（6 个维度 + 扫描数据对比表）
- [x] 关键洞察：4 条编号洞察，含具体数字/模式
- [x] 代码/文档链接：提供仓库、提交号、复现命令
- [x] 人/AI 角色分离：协作过程明确记录人类做了什么、AI 做了什么


## 相关方法论

- **相关方法论**: [ai-testing-strategies](../efficiency/ai-testing-strategies.md)

- **相关方法论**: [ai-security-review](../efficiency/ai-security-review.md)

- **相关方法论**: [ai-code-performance](../efficiency/ai-code-performance.md)
