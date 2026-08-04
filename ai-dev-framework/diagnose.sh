#!/usr/bin/env bash
# ai-dev-framework 自检脚本
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

pass() { echo -e "  ${GREEN}✅ PASS${NC} $1"; }
warn() { echo -e "  ${YELLOW}⚠️  WARN${NC} $1"; }
fail() { echo -e "  ${RED}❌ FAIL${NC} $1"; errors=$((errors + 1)); }

errors=0
base_dir="$(cd "$(dirname "$0")" && pwd)"

echo "========================================================================"
echo "  ai-dev-framework — 自检报告"
echo "========================================================================"
echo ""

# --- 1. 核心文件检查 ---
echo "┌──────────────────────────────────────────────┐"
echo "│  1. 核心文件                                  │"
echo "└──────────────────────────────────────────────┘"

[ -f "$base_dir/core/GOVERNANCE.md" ] && pass "GOVERNANCE.md" || fail "GOVERNANCE.md 缺失"
[ -f "$base_dir/core/quality-gates/gate1-prompt.md" ] && pass "gate1-prompt.md" || fail "gate1-prompt.md 缺失"
[ -f "$base_dir/core/quality-gates/gate2-implementation.md" ] && pass "gate2-implementation.md" || fail "gate2-implementation.md 缺失"
[ -f "$base_dir/core/quality-gates/gate3-audit.md" ] && pass "gate3-audit.md" || fail "gate3-audit.md 缺失"
[ -f "$base_dir/core/quality-gates/gate4-documentation.md" ] && pass "gate4-documentation.md" || fail "gate4-documentation.md 缺失"
[ -f "$base_dir/core/templates/CONTEXT.md" ] && pass "CONTEXT.md 模板" || fail "CONTEXT.md 模板缺失"
[ -f "$base_dir/core/templates/ADR.md" ] && pass "ADR.md 模板" || fail "ADR.md 模板缺失"
[ -f "$base_dir/core/templates/AGENTS.md" ] && pass "AGENTS.md 模板" || fail "AGENTS.md 模板缺失"
[ -f "$base_dir/core/templates/agent-prompt.md" ] && pass "agent-prompt.md 模板" || fail "agent-prompt.md 模板缺失"
[ -f "$base_dir/core/templates/quality-report.md" ] && pass "quality-report.md 模板" || fail "quality-report.md 模板缺失"

echo ""

# --- 2. 语言支持检查 ---
echo "┌──────────────────────────────────────────────┐"
echo "│  2. 语言支持                                  │"
echo "└──────────────────────────────────────────────┘"

languages=("go" "java" "python" "rust" "typescript" "swift" "kotlin" "ruby" "php" "csharp")

for lang in "${languages[@]}"; do
    lang_dir="$base_dir/languages/$lang"

    if [ -d "$lang_dir" ]; then
        check_file="$lang_dir/check.sh"
        rules_file="$lang_dir/rules.md"

        if [ -f "$check_file" ] && [ -f "$rules_file" ]; then
            if [ -x "$check_file" ]; then
                pass "$lang (check.sh + rules.md, 可执行)"
            else
                warn "$lang (check.sh 不可执行)"
            fi
        else
            pass "$lang"
            [ ! -f "$check_file" ] && warn "  → $lang/check.sh 缺失"
            [ ! -f "$rules_file" ] && warn "  → $lang/rules.md 缺失"
        fi
    else
        warn "$lang 目录缺失"
    fi
done

echo ""

# --- 3. 框架配置检查 ---
echo "┌──────────────────────────────────────────────┐"
echo "│  3. 框架配置                                  │"
echo "└──────────────────────────────────────────────┘"

frameworks=("react" "vue" "spring-boot" "nextjs" "fastapi" "express" "actix")

for fw in "${frameworks[@]}"; do
    if [ -f "$base_dir/frameworks/$fw/rules.md" ]; then
        pass "$fw"
    else
        warn "$fw 缺失"
    fi
done

echo ""

# --- 4. 钩子集成检查 ---
echo "┌──────────────────────────────────────────────┐"
echo "│  4. 钩子集成                                  │"
echo "└──────────────────────────────────────────────┘"

[ -f "$base_dir/hooks/opencode/hooks.json" ] && pass "opencode hooks.json" || fail "opencode hooks.json 缺失"
[ -f "$base_dir/hooks/jcode/config.yml" ] && pass "jcode config.yml" || fail "jcode config.yml 缺失"
[ -f "$base_dir/hooks/pre-commit/.pre-commit-config.yaml" ] && pass "pre-commit-config.yaml" || fail "pre-commit-config.yaml 缺失"

echo ""

# --- 5. 安装脚本检查 ---
echo "┌──────────────────────────────────────────────┐"
echo "│  5. 安装脚本                                  │"
echo "└──────────────────────────────────────────────┘"

if [ -f "$base_dir/install.sh" ]; then
    if [ -x "$base_dir/install.sh" ]; then
        pass "install.sh (可执行)"
    else
        fail "install.sh 不可执行"
    fi
else
    fail "install.sh 缺失"
fi

echo ""

# --- 6. 所有脚本可执行检查 ---
echo "┌──────────────────────────────────────────────┐"
echo "│  6. 脚本权限检查                              │"
echo "└──────────────────────────────────────────────┘"

while IFS= read -r -d '' script; do
    rel="${script#$base_dir/}"
    if [ -x "$script" ]; then
        pass "  $rel"
    else
        fail "  $rel 不可执行"
    fi
done < <(find "$base_dir" -name '*.sh' -print0 2>/dev/null)

echo ""
echo "========================================================================"
if [ $errors -eq 0 ]; then
    echo -e "  ${GREEN}✅ 所有检查通过 — 框架完整可用${NC}"
else
    echo -e "  ${RED}❌ $errors 项检查失败，请修复后再使用${NC}"
fi
echo "========================================================================"

exit $errors
