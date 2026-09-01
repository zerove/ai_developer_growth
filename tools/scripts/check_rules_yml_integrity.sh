#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# Check .adg/rules.yml integrity (防止 severity_overrides 段丢失)
# ──────────────────────────────────────────────────────────────
# Phase 28 收口后建立: 本会话两次发生 .adg/rules.yml 工作区丢失
# severity_overrides 段 (71 行) 的事件, 通过 git checkout HEAD 恢复.
# 此脚本作为前置门禁: 若 rules.yml 行数 ≠ HEAD 版本, 立即报错并提示恢复.
# ──────────────────────────────────────────────────────────────
set -e

cd "$(dirname "$0")/../.."

EXPECTED_LINES=$(git show HEAD:.adg/rules.yml 2>/dev/null | wc -l)
ACTUAL_LINES=$(wc -l < .adg/rules.yml 2>/dev/null || echo 0)

if [ "$EXPECTED_LINES" -ne "$ACTUAL_LINES" ]; then
    echo "❌ .adg/rules.yml 完整性检查失败"
    echo "   HEAD 版本: $EXPECTED_LINES 行"
    echo "   工作区:    $ACTUAL_LINES 行"
    echo "   差异:      $((EXPECTED_LINES - ACTUAL_LINES)) 行"
    echo ""
    echo "可能原因: severity_overrides 段被某次操作 (stash pop / 手动 write /"
    echo "         IDE 误编辑) 覆盖丢失."
    echo ""
    echo "恢复命令:"
    echo "   git checkout HEAD -- .adg/rules.yml"
    echo ""
    exit 1
fi

echo "✅ .adg/rules.yml 完整 ($ACTUAL_LINES 行)"
exit 0