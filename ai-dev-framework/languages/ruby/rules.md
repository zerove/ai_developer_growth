# Ruby 语言规则

> 适用于 Ruby 项目的 AI Agent 开发规则

---

## 代码风格

### 命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| 文件名 | snake_case | `my_module.rb` |
| 方法名 | snake_case | `my_method` |
| 变量名 | snake_case | `my_variable` |
| 类名 | PascalCase | `MyClass` |
| 模块 | PascalCase | `MyModule` |
| 常量 | UPPER_SNAKE_CASE | `MAX_SIZE` |

### 导入顺序

```ruby
# 1. 标准库
require 'json'
require 'yaml'

# 2. 第三方库
require 'sinatra'
require 'activerecord'

# 3. 本地模块
require_relative 'my_module'
```

---

## 错误处理

```ruby
# ✅ 正确
def my_function
  result = do_something
rescue SpecificError => e
  raise MyError, "Failed: #{e.message}"
end

# ❌ 错误
def my_function
  result = do_something rescue nil
end
```

---

## 测试

```ruby
RSpec.describe 'my_function' do
  it 'returns correct result' do
    expect(my_function(1, 2)).to eq(3)
  end

  it 'raises error for invalid input' do
    expect { my_function(nil, 2) }.to raise_error(MyError)
  end
end
```

---

*本规则适用于 Ruby 项目的 AI Agent 开发。*
