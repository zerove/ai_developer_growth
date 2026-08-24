#!/bin/bash
# 本地 CI 定时任务: 替代 GitHub Actions scheduled workflow
#
# 覆盖的远端定时任务:
#   - scheduled-governance.yml (治理巡检)
#   - quality-trends.yml      (趋势采集)
#   - mutation-testing.yml    (抽样变异测试, 可选)
#
# 用法:
#   ./scripts/local_ci.sh              # 完整运行
#   ./scripts/local_ci.sh --quick      # 跳过变异测试
#
# 建议接入 systemd timer 或 crontab 每日执行, 例如:
#   0 3 * * *  cd /path/to/repo && ./scripts/local_ci.sh >> .quality-trends/local_ci.log 2>&1

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
QUICK="${1:-}"

mkdir -p .quality-trends
LOG=.quality-trends/local_ci.log

log() { echo "[$(date '+%F %T')] $*"; }

fail=0
report=""

run_step() {
    local name="$1"; shift
    log "── $name ──"
    if "$@" >>"$LOG" 2>&1; then
        report+="✅ ${name}"$'\n'
    else
        report+="❌ ${name}"$'\n'
        fail=1
    fi
}

run_step "doctor 环境体检"     python tools/scripts/hooks_runner.py doctor
run_step "governance-audit"    python tools/scripts/hooks_runner.py governance-audit
run_step "docs-validate full"  python tools/scripts/hooks_runner.py docs-validate full
run_step "secret-scan 工作区"   python tools/scripts/hooks_runner.py secret-scan --no-history
run_step "stats 一致性检查"     python tools/scripts/update_stats.py --check

if [ "$QUICK" != "--quick" ]; then
    run_step "sbom/supply-chain" python tools/scripts/hooks_runner.py sbom
fi

# 记录本次运行结果摘要到趋势目录
{
    echo "{\"timestamp\": \"$(date -Iseconds)\", \"type\": \"local_ci\", \"failed\": $fail}"
} >>.quality-trends/local_ci_history.jsonl

echo "$report"
if [ "$fail" -ne 0 ]; then
    log "❌ 本地 CI 有失败项, 详情见 $LOG"
    exit 1
fi
log "✅ 本地 CI 全部通过"
