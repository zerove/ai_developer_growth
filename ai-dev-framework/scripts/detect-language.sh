#!/bin/bash
# 语言检测脚本

if [ -f "Cargo.toml" ]; then
    echo "rust"
elif [ -f "go.mod" ]; then
    echo "go"
elif [ -f "pom.xml" ] || [ -f "build.gradle" ]; then
    echo "java"
elif [ -f "requirements.txt" ] || [ -f "pyproject.toml" ]; then
    echo "python"
elif [ -f "package.json" ]; then
    echo "typescript"
else
    echo "unknown"
fi
