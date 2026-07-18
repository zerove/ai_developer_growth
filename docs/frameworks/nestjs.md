# NestJS Governance Rules

> 适用于 NestJS 项目的 AI Agent 开发规范。

---

## 1. 模块结构

### 模块组织

```typescript
// ✅ 正确: 模块化组织
@Module({
  imports: [TypeOrmModule.forFeature([User])],
  controllers: [UserController],
  providers: [UserService, UserRepository],
  exports: [UserService],
})
export class UserModule {}

// ❌ 禁止: 单一模块包含所有
@Module({
  controllers: [UserController, PostController, CommentController],
  providers: [UserService, PostService, CommentService],
})
export class AppModule {}
```

### 依赖注入

```typescript
// ✅ 正确
@Injectable()
export class UserService {
  constructor(
    @InjectRepository(User)
    private userRepository: Repository<User>,
  ) {}
}

// ❌ 禁止: 直接实例化
export class UserService {
  private repo = new UserRepository();  // 绕过 DI!
}
```

---

## 2. 控制器规范

### RESTful 设计

```typescript
// ✅ 正确
@Controller('users')
export class UserController {
  constructor(private readonly userService: UserService) {}
  
  @Get()
  findAll(): Promise<User[]> {
    return this.userService.findAll();
  }
  
  @Get(':id')
  findOne(@Param('id') id: string): Promise<User> {
    return this.userService.findOne(id);
  }
  
  @Post()
  create(@Body() createUserDto: CreateUserDto): Promise<User> {
    return this.userService.create(createUserDto);
  }
  
  @Put(':id')
  update(
    @Param('id') id: string,
    @Body() updateUserDto: UpdateUserDto,
  ): Promise<User> {
    return this.userService.update(id, updateUserDto);
  }
  
  @Delete(':id')
  remove(@Param('id') id: string): Promise<void> {
    return this.userService.remove(id);
  }
}
```

### DTO 验证

```typescript
// ✅ 正确
export class CreateUserDto {
  @IsString()
  @IsNotEmpty()
  name: string;
  
  @IsEmail()
  email: string;
  
  @IsEnum(Role)
  role: Role;
}

// ❌ 禁止: 无验证
export class CreateUserDto {
  name: string;
  email: string;
}
```

---

## 3. 服务规范

### 业务逻辑

```typescript
// ✅ 正确
@Injectable()
export class UserService {
  constructor(
    @InjectRepository(User)
    private userRepository: Repository<User>,
  ) {}
  
  async create(dto: CreateUserDto): Promise<User> {
    const existing = await this.userRepository.findOne({
      where: { email: dto.email },
    });
    
    if (existing) {
      throw new ConflictException('Email already exists');
    }
    
    const user = this.userRepository.create(dto);
    return this.userRepository.save(user);
  }
  
  async findAll(): Promise<User[]> {
    return this.userRepository.find();
  }
  
  async findOne(id: string): Promise<User> {
    const user = await this.userRepository.findOne({ where: { id } });
    if (!user) {
      throw new NotFoundException('User not found');
    }
    return user;
  }
}
```

### 禁止行为

```typescript
// ❌ 禁止: 在控制器中包含业务逻辑
@Controller('users')
export class UserController {
  @Post()
  async create(@Body() dto: CreateUserDto) {
    // 不应在控制器中验证业务规则
    const existing = await this.db.query(...);
    if (existing) throw new Error('Exists');
    
    return this.db.query(...);
  }
}
```

---

## 4. 中间件与管道

### 中间件

```typescript
// ✅ 正确
@Injectable()
export class LoggerMiddleware implements NestMiddleware {
  use(req: Request, res: Response, next: NextFunction) {
    console.log(`[${new Date().toISOString()}] ${req.method} ${req.path}`);
    next();
  }
}
```

### 管道

```typescript
// ✅ 正确
@Injectable()
export class ValidationPipe implements PipeTransform {
  transform(value: any, metadata: ArgumentMetadata) {
    const schema = Joi.object({
      name: Joi.string().required(),
      email: Joi.string().email().required(),
    });
    
    const { error } = schema.validate(value);
    if (error) {
      throw new BadRequestException(error.message);
    }
    return value;
  }
}
```

---

## 5. 测试规范

### 单元测试

```typescript
describe('UserService', () => {
  let service: UserService;
  let repository: Repository<User>;
  
  beforeEach(async () => {
    const module = await Test.createTestingModule({
      providers: [
        UserService,
        {
          provide: getRepositoryToken(User),
          useValue: {
            find: jest.fn(),
            findOne: jest.fn(),
            create: jest.fn(),
            save: jest.fn(),
          },
        },
      ],
    }).compile();
    
    service = module.get(UserService);
    repository = module.get(getRepositoryToken(User));
  });
  
  it('should return all users', async () => {
    const users = [{ id: '1', name: 'John' }];
    jest.spyOn(repository, 'find').mockResolvedValue(users);
    
    expect(await service.findAll()).toEqual(users);
  });
});
```

### E2E 测试

```typescript
describe('Users (e2e)', () => {
  let app: INestApplication;
  
  beforeAll(async () => {
    const module = await Test.createTestingModule({
      imports: [AppModule],
    }).compile();
    
    app = module.createNestApplication();
    await app.init();
  });
  
  afterAll(async () => {
    await app.close();
  });
  
  it('/users (GET)', () => {
    return request(app.getHttpServer())
      .get('/users')
      .expect(200)
      .expect((res) => {
        expect(Array.isArray(res.body)).toBe(true);
      });
  });
});
```

---

## 6. 项目结构

```
project/
├── src/
│   ├── modules/
│   │   ├── user/
│   │   │   ├── user.module.ts
│   │   │   ├── user.controller.ts
│   │   │   ├── user.service.ts
│   │   │   ├── dto/
│   │   │   └── entities/
│   │   └── index.ts
│   ├── common/
│   │   ├── guards/
│   │   ├── pipes/
│   │   └── interceptors/
│   └── main.ts
├── test/
├── nest-cli.json
├── package.json
└── README.md
```

---

## 7. 安全规范

### 认证

```typescript
// ✅ 正确
@Injectable()
export class JwtAuthGuard extends AuthGuard('jwt') {
  canActivate(context: ExecutionContext) {
    return super.canActivate(context);
  }
}

@Controller('users')
@UseGuards(JwtAuthGuard)
export class UserController {
  // 只有认证用户可以访问
}
```

### 密钥管理

```typescript
// ❌ 禁止
const JWT_SECRET = 'sk-1234567890';

// ✅ 正确
const JWT_SECRET = process.env.JWT_SECRET;
if (!JWT_SECRET) {
  throw new Error('JWT_SECRET not set');
}
```

---

## 8. 质量检查清单

### 代码质量

- [ ] ESLint 通过
- [ ] TypeScript 无错误
- [ ] 模块化组织
- [ ] 无直接实例化依赖
- [ ] 无硬编码密钥

### 测试质量

- [ ] 核心服务测试覆盖 > 80%
- [ ] 所有测试通过
- [ ] Mock 使用正确
- [ ] E2E 测试覆盖核心流程

### 安全

- [ ] 使用 Guards 进行认证
- [ ] DTO 验证完整
- [ ] 无 SQL 注入风险

---

*本规范随 NestJS 生态演进持续更新。最后更新: 2026-07-17*
