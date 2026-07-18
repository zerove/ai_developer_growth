# Ruby Governance Rules

> 适用于 Ruby 项目的 AI Agent 开发规范。

---

## 1. 代码规范

### 格式化

- **工具**: RuboCop
- **缩进**: 2 空格
- **行宽**: 120 字符
- **字符串**: 双引号

### Linting

- **工具**: RuboCop + reek + flog
- **规则**: 启用所有 cops
- **复杂度**: flog < 10

### 命名规范

```ruby
# ✅ 正确
class UserService
end

def get_user(id)
end

MAX_RETRIES = 3

# ❌ 禁止
class userService  # 应为 PascalCase
end

def GetUser(id)  # 应为 snake_case
end
```

---

## 2. 错误处理

### 自定义异常

```ruby
class AppError < StandardError
  attr_reader :code
  
  def initialize(message, code)
    super(message)
    @code = code
  end
end

class ValidationException < AppError
  attr_reader :field
  
  def initialize(field, message)
    super(message, 'VALIDATION_ERROR')
    @field = field
  end
end

class NotFoundException < AppError
  def initialize(resource, id)
    super("#{resource} with id #{id} not found", 'NOT_FOUND')
  end
end
```

### 禁止行为

```ruby
# ❌ 禁止: 空 rescue
begin
  do_something
rescue => e
  # 忽略
end

# ❌ 禁止: 使用异常控制流
begin
  return hash[key]
rescue
  return default_value
end

# ✅ 正确
return hash.fetch(key, default_value)
```

---

## 3. 现代 Ruby 特性

### Frozen String Literal

```ruby
# 文件头部添加
# frozen_string_literal: true

# ❌ 禁止: 可变字符串
name = "hello"
name << " world"  # FrozenError!

# ✅ 正确
name = +""  # 显式可变
name << "hello"
```

### Pattern Matching (Ruby 3.0+)

```ruby
# ✅ 正确
case user
in { name: String => name, role: 'admin' }
  puts "Admin: #{name}"
in { name: String => name }
  puts "User: #{name}"
else
  puts "Unknown"
end
```

### Ractor (Ruby 3.0+)

```ruby
# ✅ 正确: 并发执行
ractors = (1..10).map do |i|
  Ractor.new(i) do |n|
    process(n)
  end
end

results = ractors.map(&:take)
```

---

## 4. 测试规范

### RSpec

```ruby
RSpec.describe UserService do
  let(:service) { described_class.new }
  
  describe '#get_user' do
    it 'returns user when found' do
      user = service.get_user('123')
      expect(user.id).to eq('123')
    end
    
    it 'raises when not found' do
      expect { service.get_user('nonexistent') }
        .to raise_error(NotFoundException)
    end
  end
end
```

### Mock 框架

```ruby
RSpec.describe UserService do
  let(:repository) { instance_double(UserRepository) }
  let(:service) { described_class.new(repository) }
  
  it 'gets user' do
    allow(repository).to receive(:find_by_id)
      .with('123')
      .and_return(User.new('123'))
    
    user = service.get_user('123')
    expect(user).not_to be_nil
    expect(repository).to have_received(:find_by_id).with('123')
  end
end
```

---

## 5. 项目结构

```
project/
├── app/
│   ├── controllers/
│   ├── models/
│   ├── services/
│   └── repositories/
├── spec/
│   ├── controllers/
│   ├── models/
│   └── services/
├── Gemfile
└── README.md
```

---

## 6. 安全规范

### SQL 注入防护

```ruby
# ❌ 禁止: 字符串插值
User.where("name = '#{name}'")

# ✅ 正确: 参数化查询
User.where("name = ?", name)
User.where(name: name)
```

### 密钥管理

```ruby
# ❌ 禁止
API_KEY = 'sk-1234567890'

# ✅ 正确
API_KEY = ENV.fetch('API_KEY') { raise 'API_KEY not set' }
```

---

## 7. 质量检查清单

### 代码质量

- [ ] RuboCop 通过
- [ ] 无空 rescue 块
- [ ] frozen_string_literal: true
- [ ] 无硬编码密钥
- [ ] flog < 10

### 测试质量

- [ ] 核心逻辑测试覆盖 > 80%
- [ ] 所有测试通过
- [ ] Mock 使用正确
- [ ] 无共享状态

### 文档质量

- [ ] 公开方法有 YARD 文档
- [ ] 复杂逻辑有注释
- [ ] README.md 已更新

---

*本规范随 Ruby 生态演进持续更新。最后更新: 2026-07-17*
