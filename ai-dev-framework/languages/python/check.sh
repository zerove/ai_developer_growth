#!/bin/bash
# Python 质量门禁脚本

set -e

echo "🔍 检查 Python 项目..."

# 1. Ruff Lint 检查
echo "=== Ruff Lint 检查 ==="
if command -v ruff &>/dev/null; then
    ruff check . --output-format=json >/tmp/ruff-result.json 2>&1
    RUFF_ERRORS=$(python3 -c "import json; data=json.load(open('/tmp/ruff-result.json')); print(len(data))")
    if [ "$RUFF_ERRORS" -gt 0 ]; then
        echo "❌ Ruff 检查失败: $RUFF_ERRORS 个错误"
        ruff check . --output-format=text
        exit 1
    fi
    echo "✅ Ruff 检查通过"
else
    echo "⚠️  Ruff 未安装，跳过检查"
fi

# 2. 测试检查
echo "=== 测试检查 ==="
if command -v pytest &>/dev/null; then
    if pytest tests/ -q --tb=short; then
        echo "✅ 测试通过"
    else
        echo "❌ 测试失败"
        exit 1
    fi
else
    echo "⚠️  pytest 未安装，跳过检查"
fi

# 3. 类型检查 (可选)
echo "=== 类型检查 ==="
if command -v mypy &>/dev/null; then
    if mypy . --ignore-missing-imports; then
        echo "✅ 类型检查通过"
    else
        echo "⚠️  类型检查有警告"
    fi
else
    echo "⚠️  mypy 未安装，跳过检查"
fi

echo "✅ Python 质量门禁检查完成"
