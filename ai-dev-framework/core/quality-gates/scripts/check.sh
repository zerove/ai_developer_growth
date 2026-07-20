#!/bin/bash
# 质量门禁检查脚本

set -e

FRAMEWORK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../" && pwd)"
LANGUAGE="${1:-auto}"

# 检测语言
if [ "$LANGUAGE" = "auto" ]; then
    if [ -f "Cargo.toml" ]; then
        LANGUAGE="rust"
    elif [ -f "go.mod" ]; then
        LANGUAGE="go"
    elif [ -f "pom.xml" ] || [ -f "build.gradle" ]; then
        LANGUAGE="java"
    elif [ -f "requirements.txt" ] || [ -f "pyproject.toml" ]; then
        LANGUAGE="python"
    elif [ -f "package.json" ]; then
        LANGUAGE="typescript"
    else
        LANGUAGE="python"
    fi
fi

echo "使用语言配置: $LANGUAGE"

# 执行语言特定检查
if [ -f "$FRAMEWORK_DIR/languages/$LANGUAGE/check.sh" ]; then
    bash "$FRAMEWORK_DIR/languages/$LANGUAGE/check.sh"
else
    echo "⚠️  未找到语言配置: $LANGUAGE"
    echo "请手动配置检查脚本"
fi
