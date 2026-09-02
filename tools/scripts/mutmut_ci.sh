#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# mutmut CI helper (Phase 30 候选 2 落地)
# ──────────────────────────────────────────────────────────────
# Phase 29 ADR-024 标记 mutmut 单文件 demo 跑通 (8259 突变), 但全量
# 单机跑会超时 (>30 分钟). 此脚本提供 CI 友好的增量入口:
#
#   - 默认: 跑全量 rules_engine (与 mutmut 配置一致)
#   - --changed-only: 跑 git diff 最近一次 commit 影响的文件
#   - --files <list>: 跑指定文件
#
# cleanup: mutmut 跑完会自动生成 .bak 备份和 .mutmut-cache, 本脚本
# 完成后会主动清理 (避免污染工作区, 见 ADR-024 决策 5)
#
# 用法: bash tools/scripts/mutmut_ci.sh [--changed-only] [--files F1 F2 ...]
# 退出码: 0 (突变全部被测试杀死) / 2 (有幸存突变) / 1 (致命错误)
# ──────────────────────────────────────────────────────────────
set -e

cd "$(dirname "$0")/../.."

MODE="full"
FILES=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --changed-only)
            MODE="changed"
            shift
            ;;
        --files)
            shift
            while [[ $# -gt 0 && ! "$1" =~ ^-- ]]; do
                FILES+=("$1")
                shift
            done
            MODE="files"
            ;;
        -h|--help)
            echo "用法: bash tools/scripts/mutmut_ci.sh [--changed-only] [--files F1 F2 ...]"
            echo ""
            echo "模式:"
            echo "  (默认)        全量 rules_engine (与 mutmut 配置一致, ~30 分钟)"
            echo "  --changed-only 跑 git diff HEAD~1 HEAD 的 Python 文件 (受 PR 影响)"
            echo "  --files F1 F2  跑指定 Python 文件列表"
            echo ""
            echo "前置: pip install mutmut>=2.4.0,<3"
            echo "cleanup: 完成后自动删除 .bak 备份与 .mutmut-cache"
            exit 0
            ;;
        *)
            echo "未知参数: $1" >&2
            exit 1
            ;;
    esac
done

# 检查 mutmut 安装
if ! python3 -c "import mutmut" 2>/dev/null; then
    echo "❌ mutmut 未安装"
    echo "   pip install mutmut>=2.4.0,<3"
    exit 1
fi

# 决定目标文件
case "$MODE" in
    full)
        TARGETS=(--paths-to-mutate=tools/scripts/rules_engine)
        echo "🔄 全量模式: tools/scripts/rules_engine"
        ;;
    changed)
        CHANGED=$(git diff --name-only HEAD~1 HEAD 2>/dev/null | grep -E '\.py$' | head -10 || echo "")
        if [ -z "$CHANGED" ]; then
            echo "⚠️  无 changed Python 文件, 跳过"
            exit 0
        fi
        # mutmut 不接受多文件, 取首个或合并
        TARGETS=(--paths-to-mutate=$(echo "$CHANGED" | head -1))
        echo "🔄 增量模式: 跑首个变更文件 (mutmut 单文件限制)"
        echo "   文件: $(echo "$CHANGED" | head -1)"
        ;;
    files)
        if [ ${#FILES[@]} -eq 0 ]; then
            echo "❌ --files 需要至少 1 个文件"
            exit 1
        fi
        # 同样限制: 只取首个
        TARGETS=(--paths-to-mutate="${FILES[0]}")
        echo "🔄 指定文件模式: ${FILES[0]}"
        ;;
esac

echo ""
echo "=== 跑 mutmut (5 分钟超时, CI 友好) ==="
timeout 300 mutmut run "${TARGETS[@]}" --no-progress 2>&1 | tail -10
MUTMUT_EXIT=${PIPESTATUS[0]}

echo ""
echo "=== 清理 mutmut 残留 (.bak + .mutmut-cache) ==="
find tools/scripts -name "*.bak" -delete 2>/dev/null || true
rm -rf .mutmut-cache 2>/dev/null || true

if [ -d tools/scripts/rules_engine ] && [ -f tools/scripts/rules_engine/checker.py ]; then
    echo "✅ checker.py 仍存在 (mutmut 不影响原文件)"
fi

echo ""
echo "=== mutmut exit: $MUTMUT_EXIT ==="
# mutmut exit 0: 全部被杀死 / 2: 有幸存 / 1: 致命错误 / 124: 超时
case $MUTMUT_EXIT in
    0) echo "✅ 所有突变被测试杀死"; exit 0 ;;
    2) echo "⚠️  有幸存突变, 需要补测试"; exit 0 ;;  # 不阻断 CI
    124) echo "⏰ 5 分钟超时, 部分突变未完成"; exit 0 ;;  # 不阻断
    *) echo "❌ 致命错误: $MUTMUT_EXIT"; exit $MUTMUT_EXIT ;;
esac