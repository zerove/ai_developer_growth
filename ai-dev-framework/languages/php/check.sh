#!/bin/bash
# PHP 质量门禁脚本

set -e

echo "🔍 检查 PHP 项目..."

# 1. PHPStan 检查
echo "=== PHPStan 检查 ==="
if command -v phpstan &>/dev/null; then
    if phpstan analyse src/ --level=max; then
        echo "✅ PHPStan 检查通过"
    else
        echo "❌ PHPStan 检查失败"
        exit 1
    fi
elif command -v vendor/bin/phpstan &>/dev/null; then
    if vendor/bin/phpstan analyse src/ --level=max; then
        echo "✅ PHPStan 检查通过"
    else
        echo "❌ PHPStan 检查失败"
        exit 1
    fi
else
    echo "⚠️  PHPStan 未安装，跳过检查"
fi

# 2. 测试检查
echo "=== 测试检查 ==="
if command -v phpunit &>/dev/null; then
    if phpunit; then
        echo "✅ 测试通过"
    else
        echo "❌ 测试失败"
        exit 1
    fi
elif command -v vendor/bin/phpunit &>/dev/null; then
    if vendor/bin/phpunit; then
        echo "✅ 测试通过"
    else
        echo "❌ 测试失败"
        exit 1
    fi
else
    echo "⚠️  PHPUnit 未安装，跳过检查"
fi

# 3. 格式检查
echo "=== 格式检查 ==="
if command -v php-cs-fixer &>/dev/null; then
    if php-cs-fixer fix --dry-run --diff; then
        echo "✅ 格式检查通过"
    else
        echo "⚠️  格式检查有警告"
    fi
else
    echo "⚠️  php-cs-fixer 未安装，跳过检查"
fi

echo "✅ PHP 质量门禁检查完成"
