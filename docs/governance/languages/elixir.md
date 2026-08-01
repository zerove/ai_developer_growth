---
title: Elixir Governance Rules
description: > 适用于 Elixir 项目的 AI Agent 开发规范。
category: 治理层
tags: ['测试', 'AI', 'SQL', 'API']
difficulty: 初级
reading_time: 10 分钟
updated: 2026-07-21
---

# Elixir Governance Rules

> 适用于 Elixir 项目的 AI Agent 开发规范。

---

## 1. 代码规范

### 格式化

- **工具**: mix format
- **缩进**: 2 空格
- **行宽**: 98 字符
- **引号**: 双引号

### Linting

- **工具**: Credo + Dialyzer
- **规则**: 启用所有规则
- **类型检查**: Dialyzer

### 命名规范

```elixir
# ✅ 正确
defmodule UserService do
end

def get_user(id) do
end

@max_retries 3

# ❌ 禁止
defmodule userService do  # 应为 PascalCase
end

def GetUser(id) do  # 应为 snake_case
end
```

---

## 2. 模式匹配

### 函数子句

```elixir
# ✅ 正确: 使用模式匹配
def process_user(%User{role: :admin} = user) do
  process_admin(user)
end

def process_user(%User{role: :user} = user) do
  process_regular_user(user)
end

# ❌ 禁止: 使用 if/else
def process_user(user) do
  if user.role == :admin do
    process_admin(user)
  else
    process_regular_user(user)
  end
end
```

### with 语句

```elixir
# ✅ 正确: 使用 with 处理多步骤操作
def create_user(attrs) do
  with {:ok, validated} <- validate_attrs(attrs),
       {:ok, user} <- insert_user(validated),
       {:ok, _} <- send_welcome_email(user) do
    {:ok, user}
  else
    {:error, reason} -> {:error, reason}
  end
end

# ❌ 禁止: 嵌套 case
def create_user(attrs) do
  case validate_attrs(attrs) do
    {:ok, validated} ->
      case insert_user(validated) do
        {:ok, user} ->
          case send_welcome_email(user) do
            {:ok, _} -> {:ok, user}
            error -> error
          end
        error -> error
      end
    error -> error
  end
end
```

---

## 3. OTP 模式

### GenServer

```elixir
# ✅ 正确
defmodule UserService do
  use GenServer

  # Client API
  def start_link(opts) do
    GenServer.start_link(__MODULE__, opts, name: __MODULE__)
  end

  def get_user(id) do
    GenServer.call(__MODULE__, {:get_user, id})
  end

  # Server Callbacks
  @impl true
  def init(opts) do
    {:ok, %{users: %{}}}
  end

  @impl true
  def handle_call({:get_user, id}, _from, state) do
    case Map.fetch(state.users, id) do
      {:ok, user} -> {:reply, {:ok, user}, state}
      :error -> {:reply, {:error, :not_found}, state}
    end
  end
end
```

### Supervisor

```elixir
# ✅ 正确
defmodule MyApp.Supervisor do
  use Supervisor

  def start_link(opts) do
    Supervisor.start_link(__MODULE__, opts, name: __MODULE__)
  end

  @impl true
  def init(_opts) do
    children = [
      {UserService, []},
      {PostService, []}
    ]

    Supervisor.init(children, strategy: :one_for_one)
  end
end
```

---

## 4. 测试规范

### ExUnit

```elixir
defmodule UserServiceTest do
  use ExUnit.Case

  test "get_user returns user when found" do
    user = UserService.get_user("123")
    assert user.id == "123"
  end

  test "get_user returns error when not found" do
    assert {:error, :not_found} = UserService.get_user("nonexistent")
  end

  test "create_user with valid attrs" do
    attrs = %{name: "John", email: "john@example.com"}
    assert {:ok, user} = UserService.create_user(attrs)
    assert user.name == "John"
  end
end
```

### Mock 框架

```elixir
defmodule UserServiceTest do
  use ExUnit.Case
  import Mox

  setup do
    Mox.stub_with(MockUserRepo, UserRepo)
    :ok
  end

  test "get_user" do
    expect(MockUserRepo, :find, fn "123" ->
      {:ok, %User{id: "123"}}
    end)

    assert {:ok, user} = UserService.get_user("123")
    assert user.id == "123"
  end
end
```

---

## 5. 项目结构

```
project/
├── lib/
│   ├── project/
│   │   ├── application.ex
│   │   ├── user_service.ex
│   │   └── repos/
│   └── project.ex
├── test/
├── mix.exs
└── README.md
```

---

## 6. 安全规范

### 密钥管理

```elixir
# ❌ 禁止
@api_key "YOUR_API_KEY_HERE"

# ✅ 正确
@api_key System.get_env("API_KEY") || raise "API_KEY not set"
```

### SQL 注入防护

```elixir
# ❌ 禁止: 字符串拼接
Repo.query!("SELECT * FROM users WHERE id = '#{id}'")

# ✅ 正确: 使用 Ecto
Repo.get(User, id)
Repo.one(from u in User, where: u.id == ^id)
```

---

## 7. 质量检查清单

### 代码质量

- [ ] mix format 通过
- [ ] credo 无错误
- [ ] dialyzer 无警告
- [ ] 无 nil 返回
- [ ] 无硬编码密钥

### 测试质量

- [ ] 核心逻辑测试覆盖 > 80%
- [ ] 所有测试通过
- [ ] 使用 property-based 测试
- [ ] Mock 使用正确

### OTP 设计

- [ ] 正确使用 Supervisor
- [ ] 使用 GenServer 管理状态
- [ ] 监督树设计合理

---

*本规范随 Elixir 生态演进持续更新。最后更新: 2026-07-17*
