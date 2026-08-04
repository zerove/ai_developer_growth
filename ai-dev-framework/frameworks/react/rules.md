# React 开发规则

> 基于 TypeScript 的 React 开发标准，配合 .ai-framework 使用

---

## 核心约定

### 文件组织

```
src/
├── components/     # 通用组件
│   ├── common/    # 基础 UI 组件
│   └── business/  # 业务组件
├── hooks/         # 自定义 Hooks
├── pages/         # 页面组件 (Next.js 用 app/)
├── services/      # API 服务
├── store/         # 状态管理
├── types/         # 类型定义
└── utils/         # 工具函数
```

### 命名规范

- **组件文件**: `PascalCase.tsx` (Button.tsx)
- **Hook 文件**: `camelCase.ts` (useAuth.ts)
- **样式文件**: `camelCase.module.css`
- **类型文件**: `camelCase.types.ts`

### 组件设计

```tsx
// ✅ 好的组件
interface ButtonProps {
  label: string;
  variant: 'primary' | 'secondary';
  onClick: () => void;
}

export function Button({ label, variant, onClick }: ButtonProps) {
  return (
    <button className={styles[variant]} onClick={onClick}>
      {label}
    </button>
  );
}

// ❌ 坏的模式
export default function Comp(props: any) { ... }
```

---

## 质量门禁

### Lint

```bash
# 检查
npx eslint src/ --ext .ts,.tsx
npx tsc --noEmit

# 格式化
npx prettier --check src/
```

### 测试

```bash
# 组件测试
npx vitest run
# 或
npx jest --coverage
```

---

## Hooks 模式

```tsx
// ✅ 自定义 Hook
export function useUser(id: string) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchUser(id).then(data => {
      setUser(data);
      setLoading(false);
    });
  }, [id]);

  return { user, loading };
}

// ✅ 封装状态逻辑
export function useToggle(initial = false) {
  const [on, setOn] = useState(initial);
  return { on, toggle: () => setOn(v => !v), setOn };
}
```

---

## 状态管理

| 规模 | 方案 |
|------|------|
| 小型 (< 5 组件共享) | useState + props |
| 中型 (< 20 组件) | React Context + useReducer |
| 大型 | Zustand / Jotai |
| 企业级 | Redux Toolkit |

---

## 错误处理

```tsx
// ✅ 错误边界
class ErrorBoundary extends React.Component<
  { children: React.ReactNode },
  { hasError: boolean }
> {
  state = { hasError: false };

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  render() {
    if (this.state.hasError) {
      return <ErrorFallback />;
    }
    return this.props.children;
  }
}

// ✅ 异步错误
function UserProfile({ userId }: { userId: string }) {
  const { data, error, isLoading } = useQuery({
    queryKey: ['user', userId],
    queryFn: () => fetchUser(userId)
  });

  if (isLoading) return <Loading />;
  if (error) return <Error message={error.message} />;
  return <Profile data={data} />;
}
```

---

## 常用依赖

| 用途 | 推荐包 |
|------|--------|
| 路由 | react-router-dom v6 |
| 状态管理 | zustand |
| 数据获取 | @tanstack/react-query |
| 表单 | react-hook-form + zod |
| UI 组件 | shadcn/ui / radix-ui |
| 样式 | tailwindcss / CSS Modules |
