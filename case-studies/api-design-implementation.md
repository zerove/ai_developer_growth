# 案例研究：用 AI 设计与实现 REST API

## 背景

为一个内部工具构建 REST API，需要支持：
- 用户认证 (JWT)
- CRUD 操作
- 实时通知 (WebSocket)
- 数据导出 (CSV/JSON)

**约束**:
- 2 周交付
- 团队只有 1 名后端开发者
- 需要对接 3 个外部服务

这是一个典型的"时间紧、人手少"场景。一个人要在两周内完成从 API 设计到生产部署的全流程，包括认证鉴权、业务逻辑、外部集成、文档编写。传统的开发方式几乎不可能按时交付，除非大量使用现成的脚手架和样板代码。

更棘手的是，这个 API 需要对接 Stripe（支付）、SendGrid（邮件）、Twilio（短信）三个外部服务。每个服务的 API 文档都长达数百页，手动阅读和编写集成代码需要大量时间。而 AI 对这些主流服务的 API 非常熟悉，能直接生成可用的集成代码。

---

## AI 协作策略

### 阶段 1: API 设计 (半天)

**传统方式**: 手写 OpenAPI 文档，估计 2-3 天

**AI 协作 Prompt**:
```markdown
设计一个内部工具的 REST API。

**资源**:
- Users: 用户管理
- Projects: 项目管理
- Tasks: 任务管理
- Reports: 报表生成

**要求**:
1. RESTful 设计
2. JWT 认证
3. 分页、过滤、排序
4. 错误处理规范
5. 生成 OpenAPI 3.0 文档

**输出**:
- API 路由设计
- 数据模型 (Pydantic)
- OpenAPI YAML
```

**AI 输出**: 完整的 API 设计 + OpenAPI 文档

**效率提升**: 半天 vs 3 天 → **6x**

### 阶段 2: 代码生成 (1 天)

**传统方式**: 手写样板代码，估计 3-4 天

**AI 协作 Prompt**:
```markdown
基于 OpenAPI 文档生成 FastAPI 代码。

**要求**:
1. 自动生成路由处理函数
2. Pydantic 模型验证
3. 依赖注入 (数据库、认证)
4. 错误处理中间件
5. 类型注解完整

**约束**:
- 遵循 FastAPI 最佳实践
- 代码可直接运行
- 包含基本的单元测试
```

**AI 输出**: 可运行的 API 代码 + 测试

**效率提升**: 1 天 vs 4 天 → **4x**

**代码示例（AI 生成的路由）:**
```python
from fastapi import APIRouter, Depends, HTTPException
from auth import get_current_user
from models import TaskCreate, TaskResponse
from database import get_db

router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])

@router.post("/", response_model=TaskResponse, status_code=201)
async def create_task(
    task: TaskCreate,
    db = Depends(get_db),
    user = Depends(get_current_user)
):
    """创建新任务。需要认证。"""
    project = await db.get_project(task.project_id)
    if not project or project.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Project not found")
    return await db.create_task(task, creator_id=user.id)

@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: int,
    db = Depends(get_db),
    user = Depends(get_current_user)
):
    """获取任务详情。"""
    task = await db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task
```

### 阶段 3: 外部服务集成 (2 天)

**传统方式**: 阅读文档 + 调试，估计 1 周

**AI 协作 Prompt**:
```markdown
集成 Stripe 支付服务。

**需求**:
1. 创建订阅
2. 处理 Webhook
3. 查询账单

**已有代码**: [粘贴当前代码]

**要求**:
1. 异步处理 (httpx)
2. 重试机制
3. 错误处理
4. 日志记录
```

**AI 输出**: 集成代码 + 测试 + 错误处理

**效率提升**: 2 天 vs 1 周 → **3x**

---

## 遇到的挑战

### 挑战 1：OpenAPI 设计的粒度

**问题**：AI 生成的 OpenAPI 文档过于理想化，包含了很多"可以有"但当前不需要的功能（比如批量操作、软删除）。如果全部实现，两周时间远远不够。

**解决方案**：人工审查 OpenAPI 文档，将接口分为"必须实现"和"后续迭代"两个优先级。第一周只实现 MVP 接口（CRUD + 认证），WebSocket 和数据导出放到第二周。

### 挑战 2：外部服务的 Webhook 处理

**问题**：Stripe 的 Webhook 机制有特定的验证要求（签名验证），AI 生成的初始代码缺少这部分，直接处理 Webhook 数据会导致安全隐患。

**解决方案**：在 Prompt 中明确补充了安全约束，要求 AI 生成的 Webhook 处理代码必须包含签名验证、幂等性检查和错误日志。AI 一次性生成了完整的安全实现。

---

## 关键洞察

### 1. 设计先行，代码后行
AI 擅长设计阶段。先让 AI 生成 API 设计，人工审核后再写代码。这种"设计-审核-实现"的流程比边想边写效率高很多，因为设计阶段的修改成本几乎为零。

### 2. 契约驱动开发
OpenAPI 文档作为契约，AI 可以自动生成实现代码。这个流程让 API 设计和代码实现解耦，设计可以反复迭代，代码可以在设计稳定后一次性生成。

### 3. 外部集成是 AI 强项
AI 对常见服务（Stripe, Twilio, SendGrid）的 API 非常熟悉，能快速生成集成代码。相比手动阅读数百页文档，AI 直接给出可用的实现代码节省了大量时间。但需要注意，AI 的知识可能不是最新的，需要对照官方文档验证。

### 4. 人工审核不可少
AI 生成的代码需要人工审核，特别是安全相关部分（认证、权限、Webhook 验签）。在 API 设计阶段，人工审查确保了接口粒度合理，避免了过度设计。

---

## 效率对比

| 阶段 | 传统方式 | AI 协作 | 提升 |
|------|----------|---------|------|
| API 设计 | 3 天 | 半天 | 6x |
| 代码生成 | 4 天 | 1 天 | 4x |
| 外部集成 | 1 周 | 2 天 | 3x |
| 测试编写 | 3 天 | 半天 | 6x |
| **总计** | **2.5 周** | **4 天** | **4x** |

---

## 适用场景

- 新建 API 项目
- 需要快速原型
- 外部服务集成
- 文档驱动开发

---

## 适用场景

- 新建 API 项目
- 需要快速原型
- 外部服务集成
- 文档驱动开发

**典型项目特征:**
- 时间紧、人手少的交付场景
- 需要对接多个外部服务
- 要求完整的 API 文档和类型注解
- 需要快速验证业务想法

---

**📂 导航**
- [[MOC|⬅️ 返回知识地图]]
- **相关案例**: [[case-studies/ai-task-prioritizer|任务优先级工具]] | [[case-studies/legacy-refactoring|遗留代码重构]]
- **相关方法**: [[efficiency/full-cycle-workflow|全周期工作flow]] | [[learning/prompt-engineering|Prompt 工程]]
