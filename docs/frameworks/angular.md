---
title: Angular Governance Rules
description: > 适用于 Angular 项目的 AI Agent 开发规范。
category: 工具层
tags: ['AI', 'API', '测试', 'TypeScript', 'Angular']
difficulty: 高级
reading_time: 10 分钟
updated: 2026-07-21
---

# Angular Governance Rules

> 适用于 Angular 项目的 AI Agent 开发规范。

---

## 1. 组件规范

### 组件命名

```typescript
// ✅ 正确: 使用前缀
@Component({
  selector: 'app-user-card',
  template: `...`
})
export class UserCardComponent { }

// ❌ 禁止: 无前缀
@Component({
  selector: 'user-card',  // 应添加 app- 前缀
  template: `...`
})
export class UserCardComponent { }
```

### 组件结构

```typescript
// ✅ 正确: 使用信号 (Angular 16+)
@Component({
  selector: 'app-user-card',
  template: `
    <div (click)="onClick()">
      {{ user().name }}
    </div>
  `
})
export class UserCardComponent {
  user = input.required<User>();
  select = output<User>();

  onClick() {
    this.select.emit(this.user());
  }
}

// ✅ 正确: 使用 OnPush 变更检测
@Component({
  selector: 'app-user-card',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `...`
})
export class UserCardComponent { }
```

---

## 2. 服务规范

### 依赖注入

```typescript
// ✅ 正确
@Injectable({ providedIn: 'root' })
export class UserService {
  private http = inject(HttpClient);

  getUser(id: string): Observable<User> {
    return this.http.get<User>(`/api/users/${id}`);
  }
}

// ❌ 禁止: 在构造函数中注入
@Injectable()
export class UserService {
  constructor(private http: HttpClient) { }  // 应使用 inject()
}
```

### 服务设计

```typescript
// ✅ 正确: 单一职责
@Injectable({ providedIn: 'root' })
export class UserApiService {
  getUser(id: string): Observable<User> {
    return this.http.get<User>(`/api/users/${id}`);
  }
}

@Injectable({ providedIn: 'root' })
export class UserStateService {
  private users = signal<Map<string, User>>(new Map());

  getUser(id: string): User | undefined {
    return this.users().get(id);
  }
}

// ❌ 禁止: 上帝服务
@Injectable({ providedIn: 'root' })
export class UserService {
  getUser() { ... }
  createUser() { ... }
  updateUser() { ... }
  deleteUser() { ... }
  sendEmail() { ... }
  generateReport() { ... }
}
```

---

## 3. 状态管理

### Signals (推荐)

```typescript
// ✅ 正确: 使用信号
@Component({
  selector: 'app-counter',
  template: `
    <button (click)="increment()">Count: {{ count() }}</button>
  `
})
export class CounterComponent {
  count = signal(0);

  increment() {
    this.count.update(c => c + 1);
  }
}

// ✅ 正确: 使用 computed
@Component({
  selector: 'app-user-list',
  template: `
    <div>{{ userCount() }} users</div>
  `
})
export class UserListComponent {
  users = signal<User[]>([]);
  userCount = computed(() => this.users().length);
}
```

### NgRx (复杂场景)

```typescript
// ✅ 正确: 使用 NgRx SignalStore
@Injectable()
export class UserStore extends SignalStore<{ users: User[] }> {
  constructor() {
    super({ users: [] });
  }

  loadUsers = this.effect<void>((trigger$) =>
    trigger$.pipe(
      switchMap(() => this.userService.getUsers()),
      tap((users) => this.patchState({ users }))
    )
  );
}
```

---

## 4. 测试规范

### 单元测试

```typescript
describe('UserCardComponent', () => {
  let component: UserCardComponent;
  let fixture: ComponentFixture<UserCardComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [UserCardComponent]
    }).compileComponents();

    fixture = TestBed.createComponent(UserCardComponent);
    component = fixture.componentInstance;
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('should display user name', () => {
    component.user.set({ id: '1', name: 'John' });
    fixture.detectChanges();

    const el = fixture.nativeElement;
    expect(el.textContent).toContain('John');
  });
});
```

### 集成测试

```typescript
describe('UserModule', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [UserModule, HttpClientTestingModule]
    }).compileComponents();
  });

  it('should list users', () => {
    const fixture = TestBed.createComponent(UserListComponent);
    fixture.detectChanges();

    const compiled = fixture.nativeElement;
    expect(compiled.querySelector('app-user-list')).toBeTruthy();
  });
});
```

---

## 5. 项目结构

```
project/
├── src/
│   ├── app/
│   │   ├── core/
│   │   │   ├── services/
│   │   │   └── guards/
│   │   ├── features/
│   │   │   └── users/
│   │   │       ├── components/
│   │   │       ├── services/
│   │   │       └── users.routes.ts
│   │   └── shared/
│   │       └── components/
│   └── assets/
├── angular.json
├── package.json
└── README.md
```

---

## 6. 安全规范

### XSS 防护

```typescript
// ❌ 禁止: 直接插入 HTML
element.innerHTML = userContent;

// ✅ 正确: Angular 自动转译
// 模板中使用 {{ userContent }}
```

### 密钥管理

```typescript
// ❌ 禁止
const API_KEY = 'YOUR_API_KEY_HERE';

// ✅ 正确: 使用 environment
// environment.ts
export const environment = {
  production: false,
  apiKey: process.env['NG_APP_API_KEY'] || ''
};
```

---

## 7. 质量检查清单

### 代码质量

- [ ] ESLint 通过
- [ ] TypeScript 无错误
- [ ] 使用 OnPush 变更检测
- [ ] 使用信号或 RxJS
- [ ] 无硬编码密钥

### 测试质量

- [ ] 核心组件测试覆盖 > 80%
- [ ] 所有测试通过
- [ ] 使用 TestBed
- [ ] Mock 使用正确

### 性能

- [ ] 使用懒加载
- [ ] 使用 trackBy
- [ ] 避免不必要的变更检测

---

*本规范随 Angular 生态演进持续更新。最后更新: 2026-07-17*
