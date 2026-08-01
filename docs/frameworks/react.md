---
title: React Governance Rules
description: > 适用于 React 项目的 AI Agent 开发规范。
category: 工具层
tags: ['AI', 'API', '测试', 'TypeScript', 'React']
difficulty: 初级
reading_time: 10 分钟
updated: 2026-07-21
---

# React Governance Rules

> 适用于 React 项目的 AI Agent 开发规范。

---

## 1. 组件规范

### 函数组件优先

```tsx
// ✅ 正确
interface UserCardProps {
  user: User;
  onSelect: (user: User) => void;
}

export function UserCard({ user, onSelect }: UserCardProps) {
  return (
    <div onClick={() => onSelect(user)}>
      <h3>{user.name}</h3>
    </div>
  );
}

// ❌ 禁止: 类组件 (除非需要 lifecycle)
class UserCard extends React.Component<UserCardProps> {
  render() {
    return (
      <div onClick={() => this.props.onSelect(this.props.user)}>
        <h3>{this.props.user.name}</h3>
      </div>
    );
  }
}
```

### 组件命名

```tsx
// ✅ 正确
export function UserCard() { ... }
export const UserCard = () => { ... }

// ❌ 禁止
export default function() { ... }  // 匿名导出
```

---

## 2. Hooks 规范

### 自定义 Hook

```tsx
// ✅ 正确: 命名以 use 开头
function useUser(id: string) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  
  useEffect(() => {
    getUser(id)
      .then(setUser)
      .finally(() => setLoading(false));
  }, [id]);
  
  return { user, loading };
}

// ❌ 禁止: 非 use 开头的 Hook
function fetchUser(id: string) { ... }
```

### Hook 规则

```tsx
// ❌ 禁止: 在循环中使用 Hook
if (condition) {
  const [state, setState] = useState();  // 违反规则!
}

// ❌ 禁止: 在条件中使用 Hook
items.map(item => {
  const [selected, setSelected] = useState(false);  // 违反规则!
});

// ✅ 正确
function ItemList({ items }: { items: Item[] }) {
  return (
    <ul>
      {items.map(item => (
        <Item key={item.id} item={item} />
      ))}
    </ul>
  );
}

function Item({ item }: { item: Item }) {
  const [selected, setSelected] = useState(false);
  return <li onClick={() => setSelected(!selected)}>{item.name}</li>;
}
```

---

## 3. 状态管理

### 本地状态

```tsx
// ✅ 正确: 使用 useState/useReducer
function Counter() {
  const [count, setCount] = useState(0);
  
  return (
    <button onClick={() => setCount(c => c + 1)}>
      Count: {count}
    </button>
  );
}
```

### 全局状态

```tsx
// ✅ 正确: 使用 Context 或状态管理库
const UserContext = createContext<User | null>(null);

function App() {
  const [user, setUser] = useState<User | null>(null);
  
  return (
    <UserContext.Provider value={user}>
      <ChildComponent />
    </UserContext.Provider>
  );
}
```

### 禁止行为

```tsx
// ❌ 禁止: Prop Drilling
function App() {
  const [user, setUser] = useState<User | null>(null);
  return <Parent user={user} />;
}

function Parent({ user }: { user: User | null }) {
  return <Child user={user} />;
}

function Child({ user }: { user: User | null }) {
  return <GrandChild user={user} />;
}
```

---

## 4. 性能优化

### React.memo

```tsx
// ✅ 正确: 使用 memo 避免不必要的重渲染
const UserCard = React.memo(function UserCard({ user }: { user: User }) {
  return <div>{user.name}</div>;
});
```

### useMemo/useCallback

```tsx
// ✅ 正确
function App({ items }: { items: Item[] }) {
  const sorted = useMemo(() => items.sort((a, b) => a.id - b.id), [items]);
  
  const handleClick = useCallback(() => {
    console.log('clicked');
  }, []);
  
  return <List items={sorted} onClick={handleClick} />;
}
```

### 禁止行为

```tsx
// ❌ 禁止: 在渲染中创建新对象
function App() {
  return <Child style={{ color: 'red' }} />;  // 每次渲染创建新对象!
}

// ✅ 正确
const style = { color: 'red' };
function App() {
  return <Child style={style} />;
}
```

---

## 5. 测试规范

### React Testing Library

```tsx
import { render, screen, fireEvent } from '@testing-library/react';

describe('UserCard', () => {
  it('renders user name', () => {
    render(<UserCard user={{ id: '1', name: 'John' }} onSelect={() => {}} />);
    expect(screen.getByText('John')).toBeInTheDocument();
  });
  
  it('calls onSelect when clicked', () => {
    const onSelect = jest.fn();
    render(<UserCard user={{ id: '1', name: 'John' }} onSelect={onSelect} />);
    
    fireEvent.click(screen.getByText('John'));
    expect(onSelect).toHaveBeenCalledWith({ id: '1', name: 'John' });
  });
});
```

### Mock 规范

```tsx
// ✅ 正确: Mock API 调用
jest.mock('./api', () => ({
  getUser: jest.fn(),
}));

// ✅ 正确: Mock Hook
jest.mock('./useUser', () => ({
  useUser: jest.fn(),
}));
```

---

## 6. 项目结构

```
project/
├── src/
│   ├── components/
│   │   ├── UserCard/
│   │   │   ├── UserCard.tsx
│   │   │   ├── UserCard.test.tsx
│   │   │   └── index.ts
│   │   └── index.ts
│   ├── hooks/
│   ├── services/
│   ├── types/
│   └── App.tsx
├── package.json
└── README.md
```

---

## 7. 安全规范

### XSS 防护

```tsx
// ❌ 禁止: 直接插入 HTML
<div dangerouslySetInnerHTML={{ __html: userContent }} />

// ✅ 正确: React 自动转义
<div>{userContent}</div>
```

### 密钥管理

```tsx
// ❌ 禁止
const API_KEY = 'YOUR_API_KEY_HERE';

// ✅ 正确
const API_KEY = process.env.REACT_APP_API_KEY;
if (!API_KEY) {
  throw new Error('REACT_APP_API_KEY not set');
}
```

---

## 8. 质量检查清单

### 代码质量

- [ ] ESLint 通过
- [ ] TypeScript 无错误
- [ ] 无类组件 (除非必要)
- [ ] 无内联样式 (除非动态)
- [ ] 无硬编码密钥

### 测试质量

- [ ] 核心组件测试覆盖 > 80%
- [ ] 所有测试通过
- [ ] 使用 React Testing Library
- [ ] 无 snapshot 滥用

### 性能

- [ ] 使用 React.memo 避免不必要重渲染
- [ ] 使用 useMemo/useCallback 优化
- [ ] 无渲染中创建新对象

---

*本规范随 React 生态演进持续更新。最后更新: 2026-07-17*
