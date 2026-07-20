# Ruby 示例项目

> 配合 ai-dev-framework 使用的 Ruby 项目模板

---

## 项目结构

```
.
├── lib/
│   └── my_app.rb
├── spec/
│   ├── spec_helper.rb
│   └── my_app_spec.rb
├── Gemfile
├── Gemfile.lock
└── .rubocop.yml
```

---

## 质量门禁

```bash
# Lint
rubocop --fail-level warning

# 测试
bundle exec rspec

# 安全审计
bundle audit check --update
```

---

## Gemfile

```ruby
source 'https://rubygems.org'

gem 'sinatra', '~> 3.0'
gem 'puma', '~> 6.0'

group :development do
  gem 'rubocop', require: false
  gem 'rubocop-rspec', require: false
end

group :test do
  gem 'rspec'
  gem 'rack-test'
end
```
