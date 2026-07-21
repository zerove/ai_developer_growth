---
title: Shell/Bash Governance Rules
description: > 适用于: Shell 脚本 (Bash, Zsh, Sh)
category: 治理层
tags: ['测试', 'AI', 'API']
difficulty: 初级
reading_time: 10 分钟
updated: 2026-07-21
---

# Shell/Bash Governance Rules

> 适用于: Shell 脚本 (Bash, Zsh, Sh)

---

## 1. 代码规范

### 格式化

```bash
# 使用 shfmt 格式化
shfmt -i 2 -ci -bn script.sh

# 使用 shellcheck 检查
shellcheck script.sh
```

### 脚本结构

```bash
#!/usr/bin/env bash
# 脚本描述
# 作者: Name
# 日期: YYYY-MM-DD

# 严格模式
set -euo pipefail

# 全局变量
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly SCRIPT_DIR

# 函数定义
main() {
    # 主逻辑
}

# 执行
main "$@"
```

### 命名规范

```bash
# ✅ 正确 - 使用 snake_case
user_name="Alice"
get_user_data() { }
max_retry_count=3

# ✅ 正确 - 使用 UPPER_SNAKE_CASE (仅限常量)
readonly API_URL="https://api.example.com"
readonly MAX_RETRIES=3

# ✅ 正确 - 使用 _ 前缀 (内部函数)
_internal_helper() { }

# ❌ 禁止
userName="Alice"      # 应使用 snake_case
GetUserData() { }     # 应使用 snake_case
MAX_RETRIES=3          # 应使用 readonly
```

---

## 2. 错误处理

### 异常处理

```bash
# ✅ 正确 - 使用 trap 处理错误
cleanup() {
    local exit_code=$?
    rm -f "$temp_file"
    exit "$exit_code"
}
trap cleanup EXIT

# ✅ 正确 - 检查命令返回值
if ! command -v git >/dev/null 2>&1; then
    echo "Error: git is not installed" >&2
    exit 1
fi

# ✅ 正确 - 使用 || 处理错误
mkdir -p "$output_dir" || {
    echo "Failed to create directory: $output_dir" >&2
    exit 1
}

# ❌ 禁止
mkdir -p "$output_dir"  # 不检查返回值
```

### 日志记录

```bash
# ✅ 正确 - 使用日志函数
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*" >&2
}

log_error() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $*" >&2
}

# ✅ 正确 - 区分 stdout 和 stderr
echo "Result: $value"        # 正常输出
echo "Error: $error" >&2    # 错误输出

# ❌ 禁止
echo "Error: $error"        # 混淆输出
```

---

## 3. 变量处理

### 变量扩展

```bash
# ✅ 正确 - 使用 "${}" 语法
echo "${variable}"
echo "${array[@]}"
echo "${#string_length}"

# ✅ 正确 - 使用默认值
echo "${variable:-default}"
echo "${variable:=default}"
echo "${variable:?error message}"

# ✅ 正确 - 使用参数扩展
filename="${filepath##*/}"    # 获取文件名
extension="${filepath##*.}"   # 获取扩展名
dirname="${filepath%/*}"      # 获取目录名

# ❌ 禁止
echo "$variable"        # 缺少 {}
echo ${array[@]}        # 缺少引号
```

### 数组

```bash
# ✅ 正确 - 使用数组
files=("file1.txt" "file2.txt" "file3.txt")
for file in "${files[@]}"; do
    echo "$file"
done

# ✅ 正确 - 关联数组
declare -A user_info
user_info[name]="Alice"
user_info[email]="alice@example.com"

# ❌ 禁止 - 使用空格分隔的字符串
files="file1.txt file2.txt file3.txt"
for file in $files; do
    echo "$file"
done
```

---

## 4. 流程控制

### 条件语句

```bash
# ✅ 正确 - 使用 [[ ]] 语法
if [[ "$variable" == "value" ]]; then
    echo "Match"
fi

# ✅ 正确 - 使用 case 语句
case "$input" in
    start)
        start_service
        ;;
    stop)
        stop_service
        ;;
    *)
        echo "Unknown command: $input" >&2
        exit 1
        ;;
esac

# ❌ 禁止 - 使用 [ ] 语法
if [ "$variable" = "value" ]; then  # 不支持正则
    echo "Match"
fi
```

### 循环

```bash
# ✅ 正确 - 使用 for 循环
for file in *.txt; do
    process_file "$file"
done

# ✅ 正确 - 使用 while 循环
while IFS= read -r line; do
    echo "$line"
done < "$input_file"

# ✅ 正确 - 使用 until 循环
until check_condition; do
    sleep 1
done

# ❌ 禁止 - 使用 cat 管道
cat "$input_file" | while read line; do
    echo "$line"
done
```

---

## 5. 函数设计

### 函数定义

```bash
# ✅ 正确 - 使用 local 变量
get_user() {
    local user_id="$1"
    local result
    
    result=$(curl -s "/users/$user_id")
    echo "$result"
}

# ✅ 正确 - 返回值使用 echo，状态使用 return
is_valid() {
    local input="$1"
    
    if [[ "$input" =~ ^[0-9]+$ ]]; then
        return 0  # 成功
    else
        return 1  # 失败
    fi
}

# 使用
if is_valid "$value"; then
    echo "Valid"
fi

# ❌ 禁止 - 使用全局变量
result=""
get_user() {
    result=$(curl -s "/users/$1")
}
```

---

## 6. 安全性

### 输入验证

```bash
# ✅ 正确 - 验证输入
validate_input() {
    local input="$1"
    
    if [[ -z "$input" ]]; then
        echo "Error: Input is empty" >&2
        return 1
    fi
    
    if [[ ! "$input" =~ ^[a-zA-Z0-9_]+$ ]]; then
        echo "Error: Invalid characters in input" >&2
        return 1
    fi
}

# ✅ 正确 - 使用引号防止注入
rm -- "$filename"  # 使用 -- 防止文件名以 - 开头

# ❌ 禁止
rm $filename  # 文件名有空格会出错
```

### 权限管理

```bash
# ✅ 正确 - 检查权限
if [[ ! -x "$script" ]]; then
    echo "Error: Script is not executable" >&2
    exit 1
fi

# ✅ 正确 - 设置安全权限
chmod 700 "$script"
chmod 600 "$config_file"

# ❌ 禁止
chmod 777 "$script"  # 权限过于宽松
```

---

## 7. 测试

```bash
# ✅ 正确 - 使用 bats 测试
#!/usr/bin/env bats

setup() {
    load '../test_helper'
}

@test "get_user returns user data" {
    run get_user 1
    [ "$status" -eq 0 ]
    [[ "$output" == *"Alice"* ]]
}

@test "get_user handles invalid id" {
    run get_user 999
    [ "$status" -eq 1 ]
    [[ "$output" == *"not found"* ]]
}
```

---

## 8. 性能优化

### 并行执行

```bash
# ✅ 正确 - 使用后台任务
for file in *.txt; do
    process_file "$file" &
done
wait

# ✅ 正确 - 使用 xargs 并行
find . -name "*.txt" | xargs -P 4 -I {} process_file {}

# ❌ 禁止 - 顺序执行
for file in *.txt; do
    process_file "$file"  # 串行执行
done
```

### 缓存

```bash
# ✅ 正确 - 使用临时文件
temp_file=$(mktemp)
trap 'rm -f "$temp_file"' EXIT

# ✅ 正确 - 使用管道避免临时文件
process_data | transform | output

# ❌ 禁止 - 创建过多临时文件
tmp1=$(mktemp)
tmp2=$(mktemp)
tmp3=$(mktemp)
```

---

## 9. 禁止行为

| 行为 | 原因 |
|------|------|
| 使用 `eval` | 安全风险 |
| 使用 `cat` 管道 | 使用 `while read` |
| 使用 `grep` 管道 | 使用 `[[ =~ ]]` |
| 使用 backticks `` `command` `` | 使用 `$(command)` |
| 使用 `source` (非 POSIX) | 使用 `.` |
| 使用 `function` 关键字 | 使用 `funcname() { }` |

---

*最后更新: 2026-07-21*
