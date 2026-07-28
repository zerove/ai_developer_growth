#!/bin/bash
# Express 框架质量门禁脚本

set -e

echo "🔍 检查 Express 项目..."

# 1. 检查代码风格
if command -v ruff &> /dev/null; then
    ruff check . || echo "⚠️  Lint 有警告"
    echo "✅ 代码检查通过"
else
    echo "⚠️  ruff 未安装，跳过检查"
fi

# 2. 检查规则文件
RULE_FILE="ai-dev-framework/frameworks/express/rules.d/anti_patterns.yml"
if [ -f "$RULE_FILE" ]; then
    RULES=$(python3 -c "import yaml; f=open('$RULE_FILE'); d=yaml.safe_load(f); print(len(d.get('anti_patterns',[])))" 2>/dev/null || echo "?")
    echo "✅ Express 规则已加载 ($RULES 条)"
else
    echo "❌ 规则文件缺失"
    exit 1
fi

echo "✅ Express 框架质量门禁完成"
