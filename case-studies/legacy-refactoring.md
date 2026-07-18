# 案例研究：用 AI 重构遗留代码库

## 背景

接手一个 3 年前的 Python 项目，代码混乱、无测试、文档缺失。目标是重构为核心模块，同时保证业务连续性。

**挑战**:
- 10 万行代码，无测试覆盖
- 关键业务逻辑散落在各处
- 无文档，原开发者已离职
- 团队对核心模块充满恐惧，不敢修改

这个项目是一个内部运营系统，包含用户管理、订单处理、报表生成等核心模块。原开发者离职后，团队只敢做最小修改，不敢触碰核心逻辑。每次修 bug 都在战战兢兢中进行，因为没有任何测试来验证改动是否引入了新的问题。更糟糕的是，代码中充斥着"意大利面条式"的函数调用：一个函数 800 行，里面嵌套了 8 层 if-else，业务逻辑和数据库操作混在一起。重构的直接动机是一次线上事故：因为害怕改动核心代码，团队绕了一个大弯实现了一个简单的功能变更，结果引入了更隐蔽的 bug。这次事故让团队下定决心，必须系统性地解决技术债务。

---

## AI 协作策略

### 阶段 1: 代码理解 (2 小时)

**传统方式**: 人工阅读代码，估计 2-3 周

**AI 协作 Prompt**:
```markdown
请分析这个 Python 项目的架构。

**任务**:
1. 识别核心业务模块
2. 绘制模块依赖图 (Mermaid)
3. 找出循环依赖
4. 标注高风险区域 (复杂度高、无测试)

**输出格式**:
- 架构概览图
- 模块清单 (名称、职责、行数、测试覆盖)
- 风险评级 (高/中/低)
```

**AI 输出**: 清晰的架构图 + 模块清单 + 风险标注。其中标注了 3 个高风险模块（auth、order、payment），这些模块行数最多、复杂度最高、且没有任何测试覆盖。

**效率提升**: 2 小时 vs 2 周 → **50x**

### 阶段 2: 测试补充 (1 天)

**传统方式**: 人工编写测试，估计 1-2 周

**AI 协作 Prompt**:
```markdown
为核心模块补充单元测试。

**模块**: auth.py (用户认证)

**要求**:
1. 覆盖所有公开函数
2. 包含正常流程和异常流程
3. 使用 pytest + mock
4. 测试数据自动生成

**约束**:
- 不修改源代码
- 测试必须可独立运行
```

**AI 输出**: 完整的测试套件，覆盖率 85%+。测试不仅覆盖了正常的登录/登出流程，还自动推断出了边界情况：过期 token 处理、并发登录、密码暴力破解防护。

**效率提升**: 1 天 vs 2 周 → **10x**

**代码示例（AI 生成的测试）:**
```python
import pytest
from unittest.mock import patch, MagicMock
from auth import AuthService, AuthenticationError

class TestAuthService:
    def setup_method(self):
        self.service = AuthService(secret_key="test-key")

    @patch("auth.db.query")
    def test_login_success(self, mock_query):
        mock_query.return_value = MagicMock(
            password_hash="hashed-password",
            user_id=123,
            is_active=True
        )
        token = self.service.login("user@example.com", "correct-password")
        assert token is not None
        assert "user_id" in self.service.verify_token(token)

    def test_login_wrong_password(self):
        with pytest.raises(AuthenticationError, match="Invalid credentials"):
            self.service.login("user@example.com", "wrong-password")

    def test_token_expiry(self):
        token = self.service.login("user@example.com", "password")
        # 模拟时间流逝
        with patch("auth.time") as mock_time:
            mock_time.return_value = time.time() + 7200  # 2 小时后
            with pytest.raises(AuthenticationError, match="Token expired"):
                self.service.verify_token(token)
```

### 阶段 3: 渐进式重构 (3 天)

**策略**: 不做大爆炸重构，而是模块化渐进

**AI 协作 Prompt**:
```markdown
重构 auth 模块。

**当前状态**: [粘贴代码]

**重构目标**:
1. 提取认证逻辑为独立类
2. 支持多种认证方式 (JWT, Session)
3. 添加依赖注入
4. 保持向后兼容

**约束**:
- 所有现有测试必须通过
- API 接口不变
- 分步提交 (每步一个原子变更)
```

**AI 输出**: 重构后的代码 + 迁移指南。每个变更都是原子提交，方便 code review 和回滚。

**效率提升**: 3 天 vs 3 周 → **7x**

**代码示例（AI 重构后的认证模块）:**
```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta

@dataclass
class AuthResult:
    success: bool
    token: str | None = None
    user_id: int | None = None
    error: str | None = None

class AuthProvider(ABC):
    @abstractmethod
    def authenticate(self, credentials: dict) -> AuthResult: ...

    @abstractmethod
    def validate_token(self, token: str) -> dict: ...

class JWTProvider(AuthProvider):
    def __init__(self, secret_key: str, expiry_hours: int = 2):
        self.secret_key = secret_key
        self.expiry_hours = expiry_hours

    def authenticate(self, credentials: dict) -> AuthResult:
        user = db.find_user(credentials["email"])
        if not user or not verify_password(credentials["password"], user.password_hash):
            return AuthResult(success=False, error="Invalid credentials")
        token = self._create_token(user)
        return AuthResult(success=True, token=token, user_id=user.id)

    def validate_token(self, token: str) -> dict:
        payload = jwt.decode(token, self.secret_key, algorithms=["HS256"])
        if datetime.fromtimestamp(payload["exp"]) < datetime.now():
            raise AuthenticationError("Token expired")
        return payload

class AuthService:
    def __init__(self, provider: AuthProvider):
        self.provider = provider

    def login(self, email: str, password: str) -> str:
        result = self.provider.authenticate({"email": email, "password": password})
        if not result.success:
            raise AuthenticationError(result.error)
        return result.token
```

---

## 遇到的挑战

### 挑战 1：隐式依赖

**问题**：代码中存在大量隐式全局依赖。数据库连接通过全局变量传递，配置通过 `os.environ` 直接读取，日志通过 `print` 输出到 stdout。这些隐式依赖让函数的输入输出边界模糊不清，AI 生成的测试需要大量的 mock 工作。

**解决方案**：分两步走。第一步，让 AI 分析所有函数的隐式依赖（数据库、配置、文件系统），生成完整的依赖关系清单。第二步，逐个函数添加参数注入，保持接口兼容的同时将隐式依赖变为显式参数。

### 挑战 2：业务逻辑理解

**问题**：有些业务规则只存在于代码中，没有任何文档说明。比如"订单金额超过 10000 自动打 9 折"这个规则，在代码中只是一个 `if amount > 10000: price *= 0.9`，没有注释解释为什么。更棘手的是，有些规则之间存在隐式依赖：折扣计算在税前还是税后执行，直接影响最终金额。

**解决方案**：让 AI 分析代码中的业务逻辑，自动生成业务规则文档。对于不确定的规则，AI 会标注"需要人工确认"。最终生成了一份包含 47 条业务规则的文档，其中 12 条需要与产品经理确认。这份文档不仅帮助了重构工作，还填补了项目文档的空白。

**代码示例（AI 生成的依赖分析输出）:**
```python
# AI 分析出的隐式依赖关系图
# auth.py 依赖:
#   - os.environ["DB_URL"] (全局配置)
#   - db.connection (全局数据库连接)
#   - print() (stdout 日志)
#
# order.py 依赖:
#   - auth.get_current_user() (隐式认证)
#   - payment.process_payment() (硬编码支付模块)
#   - config.DISCOUNT_RULES (全局配置字典)
#
# 重构建议: 通过依赖注入消除隐式依赖
# 1. AuthService 接受 DB 连接作为参数
# 2. OrderService 接受 AuthService 和 PaymentService 作为参数
# 3. 配置通过 Config dataclass 注入，不再直接读取 os.environ
```

---

## 最终结果

重构完成后，项目发生了显著变化。测试覆盖率从 0% 提升到 85%+，核心模块的圈复杂度从平均 15 降低到 5 以下。团队终于可以自信地修改代码，每次提交都有测试守护。新加入的开发者通过 AI 生成的架构文档，半天就能理解系统全貌，而不是以前需要两周的"考古"时间。代码质量的提升也带来了团队信心的恢复，大家不再害怕修改核心模块。

最意外的收获是业务规则文档。AI 分析代码生成的 47 条业务规则文档，成了产品团队的重要参考资料。很多之前只有原开发者知道的隐式规则，现在被显式记录了下来。这份文档的价值甚至超过了重构本身。

---

## 关键洞察

### 1. AI 是代码考古工具
对于遗留代码，AI 的最大价值不是写新代码，而是**理解旧代码**。它能快速识别模式、依赖和风险。在一个 10 万行的代码库中，AI 只用 2 小时就完成了"代码考古"工作，包括识别核心模块、绘制依赖图、标注高风险区域。这种能力让"接手遗留项目"从噩梦变成了可控的任务。

### 2. 测试先行是安全网
在重构前补充测试，AI 可以快速生成高覆盖率测试。这为重构提供了安全网。特别值得注意的是，AI 生成的测试不仅覆盖了正常流程，还能自动推断出边界情况和异常流程。在这个案例中，AI 生成的测试发现了 3 个原代码中的潜在 bug（空指针、越界访问、类型混淆），修复后才开始正式重构。这种"先测试再重构"的顺序，是整个项目能安全完成的关键。测试覆盖率从 0% 到 85% 只用了 1 天，这是传统方式无法想象的速度。
### 3. 渐进式优于大爆炸

AI 擅长小步快跑。每次重构一个模块，验证通过后再进行下一个。这种策略降低了风险，也让团队能随时回滚到稳定状态。在实践中，我们将 8 个核心模块分为 4 个批次重构，每个批次完成后运行全量测试。有 2 次重构引入了回归问题，因为有测试守护，在 10 分钟内就定位并修复了。

**代码示例（原子提交策略）:**
```bash
# 第 1 步：提取认证接口（不改变行为）
git commit -m "refactor(auth): extract AuthProvider interface"

# 第 2 步：实现 JWTProvider（新功能，不影响旧代码）
git commit -m "feat(auth): add JWTProvider implementation"

# 第 3 步：添加依赖注入（接口兼容）
git commit -m "refactor(auth): inject dependencies instead of globals"

# 第 4 步：删除旧代码（确认新代码稳定后）
git commit -m "refactor(auth): remove legacy session-based auth"
```
### 4. 文档即上下文

让 AI 生成的文档（架构图、模块说明）成为后续工作的上下文。这些文档帮助新加入的开发者快速理解系统，也让 AI 在后续任务中能给出更准确的建议。实践中发现，当 AI 读取了自己之前生成的架构文档后再进行重构，输出质量明显提升，因为它已经"理解"了系统全貌。这种"AI 生成文档 → 文档辅助 AI 工作"的正循环，是高效 AI 协作的关键模式。

**AI 生成的架构文档示例:**
```markdown
# 模块依赖关系

## 核心模块
- auth.py (用户认证) → 依赖 db.py, config.py
- order.py (订单处理) → 依赖 auth.py, payment.py, db.py
- payment.py (支付处理) → 依赖 config.py, stripe_client.py
- report.py (报表生成) → 依赖 order.py, db.py

## 重构优先级 (基于风险和依赖)
1. config.py (基础，无依赖) → 先重构
2. auth.py (被 order.py 依赖) → 第二
3. payment.py (外部集成) → 第三
4. order.py (依赖最多，最复杂) → 最后
```

---

## 效率对比

| 阶段 | 传统方式 | AI 协作 | 提升 |
|------|----------|---------|------|
| 代码理解 | 2 周 | 2 小时 | 50x |
| 测试补充 | 2 周 | 1 天 | 10x |
| 模块重构 | 3 周 | 3 天 | 7x |
| 文档编写 | 1 周 | 2 小时 | 20x |
| **总计** | **8 周** | **5 天** | **8x** |

整个项目从"没人敢碰"到"可以安全维护"，只用了 5 个工作日。最大的时间节省来自代码理解阶段，AI 将 2 周的"考古"工作压缩到 2 小时，而且输出的架构图和模块清单比人工整理的更清晰完整。

---

## 适用场景

- 接手遗留项目
- 无测试的代码库
- 需要理解的复杂系统
- 渐进式现代化
- 团队人员变动后的知识传承
- 技术债务清理

**典型项目特征:**
- 代码量 5 万-50 万行
- 测试覆盖率 < 20%
- 原核心开发者已离职
- 团队对修改核心代码有恐惧心理
- 文档缺失或严重过时
- 技术栈老化但仍在维护

---

**📂 导航**
- [[MOC|⬅️ 返回知识地图]]
- **相关案例**: [[case-studies/ai-task-prioritizer|任务优先级工具]] | [[case-studies/ai-context-sync-development|AI-Context-Sync]]
- **相关方法**: [[learning/ai-learning-method|AI 学习法]] | [[efficiency/full-cycle-workflow|全周期工作flow]]
