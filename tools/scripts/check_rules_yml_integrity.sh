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
# v1.2 新增 (自定义规则活体校验): 三类检查, 防止再次出现
#   custom_rules 段整体丢失 (历史曾因解析死掉导致段"看似存在实则无效"):
#   1. custom_rules 段存在且每条规则含 id/pattern/message/severity 字段
#   2. severity_overrides 值必须属于合法集合 (info/warning/error/off/ignore/disabled)
#   3. 新增的 off 禁用条目 (py-missing-all / py-print-statement) 必须存在
#
# 用法: bash tools/scripts/check_rules_yml_integrity.sh
# 退出码: 0 通过 / 1 校验失败
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

# ── v1.2 检查 1: custom_rules 段存在 + 每条规则字段完整 ──
# 注意: 规则列表项 `- ...` 位于列 0, 不得被误判为顶层 key 终止 section;
# 顶层 key 形如 `installed_packs:` (字母开头), 故终止条件排除 `-` 开头行
CUSTOM_SECTION=$(awk '/^custom_rules:/{flag=1; next} /^[^[:space:]#]/ && !/^-/ {flag=0} flag && !/^[[:space:]]*#/' .adg/rules.yml)

if [ -z "$CUSTOM_SECTION" ]; then
    echo "❌ .adg/rules.yml custom_rules 段丢失 (自定义规则全部静默失效)"
    echo "   恢复命令: git checkout HEAD -- .adg/rules.yml"
    exit 1
fi

RULE_COUNT=$(printf '%s\n' "$CUSTOM_SECTION" | grep -cE "^- " || true)
if [ "$RULE_COUNT" -eq 0 ]; then
    echo "❌ .adg/rules.yml custom_rules 段无任何规则条目"
    exit 1
fi

for field in id pattern message severity; do
    FIELD_COUNT=$(printf '%s\n' "$CUSTOM_SECTION" | grep -cE "^[[:space:]]+${field}:" || true)
    if [ "$FIELD_COUNT" -lt "$RULE_COUNT" ]; then
        echo "❌ .adg/rules.yml custom_rules 字段不完整: ${field} (${FIELD_COUNT}/${RULE_COUNT} 条)"
        exit 1
    fi
done

# ── v1.2 检查 2: severity_overrides 值必须属于合法集合 ──
# 合法值: 降级三档 + 禁用三别名 (off/ignore/disabled -> enabled=False)
INVALID_OVERRIDES=$(awk '/^severity_overrides:/{flag=1; next} /^[^[:space:]#]/{flag=0} flag && /^[[:space:]]+[a-z0-9-]+:/ && $0 !~ /^[[:space:]]*#/ {print}' .adg/rules.yml | while IFS= read -r line; do
    val="${line#*:}"
    val="${val// /}"
    case "$val" in
        info|warning|error|off|ignore|disabled) ;;
        *) printf '%s\n' "$line" ;;
    esac
done)

if [ -n "$INVALID_OVERRIDES" ]; then
    echo "❌ .adg/rules.yml severity_overrides 存在非法值 (仅允许 info/warning/error/off/ignore/disabled):"
    printf '%s\n' "$INVALID_OVERRIDES"
    echo "   注意: 未知 severity 不会禁用规则 (只降为 rank-3 展示), 禁用必须用 off"
    exit 1
fi

# ── v1.2 检查 3: off 禁用条目必须在位 (防段丢失回潮) ──
OFF_RULES=("py-missing-all" "py-print-statement")
for rule in "${OFF_RULES[@]}"; do
    if ! grep -qE "^[[:space:]]*${rule}:[[:space:]]*off[[:space:]]*$" .adg/rules.yml; then
        echo "❌ .adg/rules.yml severity_overrides 缺失禁用条目: ${rule}: off"
        echo "   恢复命令: git checkout HEAD -- .adg/rules.yml"
        exit 1
    fi
done

# 计数: 当前工作区已登记的降级规则数 (动态校验新增是否同步 pyproject)
CURRENT_COUNT=$(grep -cE "^\s*[a-z-]+:\s*info\s*$" .adg/rules.yml 2>/dev/null || echo 0)
echo "✅ .adg/rules.yml severity_overrides 段完整 (${CURRENT_COUNT} 个降级规则, 含新增)"
exit 0