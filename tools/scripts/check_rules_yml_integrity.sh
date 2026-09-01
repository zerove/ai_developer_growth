#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# Check .adg/rules.yml integrity (防止 severity_overrides 段关键规则丢失)
# ──────────────────────────────────────────────────────────────
# Phase 28 收口后建立: 本会话两次发生 .adg/rules.yml 工作区丢失
# severity_overrides 段的事件, 通过 git checkout HEAD 恢复.
#
# v1.1 改进 (Phase 29): 原版用 wc -l 行数比对 HEAD, 但合法新增规则也会
#   触发误报 (本次会话改一行就 +5 行). 新版改为关键规则 key 校验:
#   HEAD 中存在的 16 类降级规则必须在工作区仍存在 (防止段丢失).
#
# 用法: bash tools/scripts/check_rules_yml_integrity.sh
# 退出码: 0 通过 / 1 关键规则丢失
# ──────────────────────────────────────────────────────────────
set -e

cd "$(dirname "$0")/../.."

# 关键规则列表 (同步 .adg/rules.yml severity_overrides 段, ADR-023 累计 17 类)
CRITICAL_RULES=(
    "py-log-print"
    "common-empty-except-block"
    "py-no-input-validation"
    "py-pip-audit-missing"
    "py-test-sleep"
    "common-debugger"
    "common-weak-hash"
    "common-unsafe-yaml-load"
    "common-http-url"
    "py-missing-type-hints"
    "py-any-type"
    "common-type-any"
    "py-global-statement"
    "py-shared-mutable"
    "py-n-plus-one"
    "py-ci-disabled-check"
    "py-file-leak"
)

MISSING=()
if [ -f .adg/rules.yml ]; then
    for rule in "${CRITICAL_RULES[@]}"; do
        # 关键规则必须存在且仍映射到 info 降级
        if ! grep -qE "^\s*${rule}:\s*info\s*$" .adg/rules.yml 2>/dev/null; then
            MISSING+=("$rule")
        fi
    done
else
    echo "❌ .adg/rules.yml 文件不存在"
    exit 1
fi

if [ ${#MISSING[@]} -gt 0 ]; then
    echo "❌ .adg/rules.yml severity_overrides 段关键规则丢失"
    echo "   丢失规则: ${MISSING[*]}"
    echo ""
    echo "可能原因: severity_overrides 段被某次操作 (stash pop / 手动 write /"
    echo "         IDE 误编辑) 覆盖丢失."
    echo ""
    echo "恢复命令:"
    echo "   git checkout HEAD -- .adg/rules.yml"
    echo ""
    exit 1
fi

# 计数: 当前工作区已登记的降级规则数 (动态校验新增是否同步 pyproject)
CURRENT_COUNT=$(grep -cE "^\s*[a-z-]+:\s*info\s*$" .adg/rules.yml 2>/dev/null || echo 0)
echo "✅ .adg/rules.yml severity_overrides 段完整 (${CURRENT_COUNT} 个降级规则, 含新增)"
exit 0