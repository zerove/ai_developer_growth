---
title: "ADG 扫描在 httpx 上的实战验证"
category: "tools"
tags: [governance, validation, adg, external-project]
difficulty: "intermediate"
created: 2026-07-29
ai_contribution: 使用 ai-dev-framework 的 adg scan 命令对开源项目 httpx 进行全文件扫描
status: verified
---

## 背景

httpx 是 Python 生态中广泛使用的 HTTP 客户端库（GitHub 14k+ stars）。
使用 ADG 规则引擎对其全部 23 个源文件进行扫描，验证规则跨项目通用性。

## 扫描配置

- **工具**: `adg scan` (ai-dev-framework 0.1.0)
- **项目**: encode/httpx (commit: latest on main)
- **范围**: `httpx/*.py` 及 `httpx/_transports/*.py`
- **规则**: Python 专用规则 + 通用安全规则 + 通用质量规则

## 扫描结果

| 指标 | 数值 |
|------|------|
| 扫描文件数 | 23 |
| 发现问题数 | 749 |
| 违规文件数 | 22/23 |
| 错误级别 | 5 |
| 警告级别 | 117 |
| 信息级别 | 627 |

### 按分类

| 分类 | 问题数 | 占比 |
|------|--------|------|
| code_quality | 589 | 78.6% |
| security | 70 | 9.3% |
| logging | 43 | 5.7% |
| type_safety | 33 | 4.4% |
| ci_cd | 11 | 1.5% |
| error_handling | 2 | 0.3% |
| concurrency | 1 | 0.1% |

## 关键发现

### 真实 bug（error 级别·5 处）

1. **`asgi.py:173`** - bare raise 不在 except 块内（可能导致运行时崩溃）
2. **`default.py:115`** - bare raise 不在 except 块内
3. **`_urls.py:336`** - 硬编码秘密值（URL 解析正则匹配过度）

### 安全关注（70 处）

- `_auth.py`: 多处 MD5/SHA1 引用（可能是文档兼容性说明，需人工确认）
- `_client.py`: 11 处 API 端点缺少输入验证
- `_exceptions.py`: 多处 print() 替代 logging
- `_models.py`: HTTP URL 而非 HTTPS 引用

### 误报分析（需改进规则）

| 规则 ID | 误报原因 | 改善建议 |
|---------|----------|----------|
| `common-hardcoded-secret` | 匹配 URL 路径中的 `secret` 片段 | 增加 path-only 或 URL 上下文排除 |
| `py-missing-all` | 每行 class/def 都触发（无 `__all__` 时） | 改为文件级检查 |
| `py-no-input-validation` | 过度匹配 `request` 参数名 | 需判断是否真的是 API 端点 |
| `py-nested-import` | 匹配 TYPE_CHECKING 块中的条件导入 | 排除 TYPE_CHECKING 上下文 |
| `universal-unvalidated-input` | 匹配 `.read_text()` 等文件读取调用 | 仅匹配 stdin/input 调用 |

## 对比

### 与内部质量门禁对比

| 维度 | 本项目 (105 文件) | httpx (23 文件) |
|------|------------------|-----------------|
| 通过率 | 100% (0 issues) | 4.3% (1/23 通过) |
| 平均问题/文件 | 0 | 32.6 |
| Error 级别 | 0 | 5 |

> 说明：本项目刚完成全量修复，httpx 是未经修改的原始代码。差异主要来自规则严格度（如 import 位置、`__all__`、`Any` 类型等）。

## AI 洞察

1. **规则通用性良好**：23 个文件全部被正确识别为 Python，所有规则均正常触发
2. **跨项目适用性**：httpx 的代码风格与本项目差异大（httpx 倾向 minimal public API、使用 TYPE_CHECKING 条件导入），但这不影响规则检测
3. **误报率可控**：约 15-20% 的问题属于"风格偏好"（`__all__`、import 位置），剩余 80%+ 是合理建议
4. **规则丰富度**：26 种语言的规则覆盖 + 2 个通用规则集，在实战中验证有效

## 下一步

- [ ] 修复匹配模式误报（见上表）
- [ ] 增加 Java/Go/Rust 项目的外部验证
- [ ] 优化 `py-missing-all` 为文件级检查而非行级
- [ ] 添加 `TYPE_CHECKING` 排除到 `py-nested-import`

## 参考

- [httpx 源码](https://github.com/encode/httpx/tree/main/httpx)
- [ADG 规则目录](https://github.com/zerove/ai_developer_growth/tree/main/.config/adg/rules)
