# Git Workflow Governance Rules

> 适用于 Git 工作流的 AI Agent 开发规范。

---

## 1. 分支策略

### GitFlow

```
main (production)
  |
  +-- develop (integration)
  |     |
  |     +-- feature/user-auth
  |     +-- feature/payment
  |     |
  |     +-- release/v1.2.0
  |     |
  +-- hotfix/critical-bug
```

### Trunk-Based Development

```
main (trunk)
  |
  +-- feature/user-auth (短命分支)
  +-- feature/payment (短命分支)
  +-- fix/bug-123 (短命分支)
```

### 分支命名

```
# ✅ 正确
feature/user-authentication
feature/payment-integration
bugfix/login-error
hotfix/security-patch
release/v1.2.0

# ❌ 禁止
johns-branch
test
temp
new-feature
```

---

## 2. 提交规范

### Conventional Commits

```
# ✅ 正确
feat(auth): add JWT authentication
fix(api): handle null response
docs(readme): update installation guide
refactor(service): extract validation logic
test(user): add unit tests
chore(deps): update dependencies

# ❌ 禁止
update code
fix bug
add feature
WIP
```

### 提交粒度

```python
# ✅ 正确: 原子提交
# 提交 1: 添加 User 模型
feat(models): add User model

# 提交 2: 添加 User 服务
feat(services): add UserService

# 提交 3: 添加 User API
feat(api): add User endpoints

# ❌ 禁止: 巨型提交
feat: add complete user module
# 包含模型、服务、API、测试、文档
```

---

## 3. Pull Request 规范

### PR 模板

```markdown
## 描述
简要描述此 PR 的内容

## 变更类型
- [ ] 新功能 (feat)
- [ ] Bug 修复 (fix)
- [ ] 文档更新 (docs)
- [ ] 重构 (refactor)
- [ ] 测试 (test)

## 测试
- [ ] 单元测试通过
- [ ] 集成测试通过
- [ ] 手动测试完成

## 截图 (如适用)
无
```

### PR 规模

```
# ✅ 正确: 小型 PR
< 200 行变更
聚焦单一功能或修复
易于审查

# ❌ 禁止: 大型 PR
> 1000 行变更
多个功能混合
难以审查
```

---

## 4. 代码审查

### 审查清单

```markdown
## 功能性
- [ ] 代码实现是否符合需求
- [ ] 边界情况是否处理
- [ ] 错误处理是否完整

## 代码质量
- [ ] 代码是否清晰易读
- [ ] 是否遵循项目规范
- [ ] 是否有重复代码

## 测试
- [ ] 是否有测试覆盖
- [ ] 测试是否充分
- [ ] 测试是否清晰

## 安全性
- [ ] 是否有安全漏洞
- [ ] 敏感信息是否保护
- [ ] 输入验证是否完整
```

### 审查反馈

```markdown
# ✅ 正确: 具体的反馈
在 `UserService.create` 方法中，应该验证 email 格式：
\`\`\`python
if not re.match(r'^[^@]+@[^@]+\.[^@]+$', email):
    raise ValidationError('Invalid email format')
\`\`\`

# ❌ 禁止: 模糊的反馈
这个代码需要改进
```

---

## 5. 合并策略

### Squash Merge

```bash
# ✅ 正确: 使用 squash merge (保持主分支清洁)
git checkout main
git merge --squash feature/user-auth
git commit -m "feat(auth): add JWT authentication"
```

### Rebase

```bash
# ✅ 正确: 使用 rebase (保持线性历史)
git checkout feature/user-auth
git rebase main
git checkout main
git merge feature/user-auth
```

### 合并前检查

```bash
# ✅ 正确: 合并前检查
git checkout feature/user-auth
git fetch origin
git rebase origin/main
npm test
npm run lint
git push origin feature/user-auth
```

---

## 6. 版本管理

### 语义化版本

```
# ✅ 正确: MAJOR.MINOR.PATCH
1.0.0  # 初始版本
1.0.1  # Bug 修复
1.1.0  # 新功能 (向后兼容)
2.0.0  # 重大变更 (不向后兼容)
```

### 标签

```bash
# ✅ 正确: 打标签
git tag -a v1.0.0 -m "Release version 1.0.0"
git push origin v1.0.0
```

---

## 7. 工作流示例

### 功能开发流程

```bash
# 1. 创建功能分支
git checkout main
git pull origin main
git checkout -b feature/user-auth

# 2. 开发
git add .
git commit -m "feat(auth): add User model"
git push origin feature/user-auth

# 3. 创建 PR
# 在 GitHub/GitLab 上创建 PR

# 4. 代码审查
# 处理审查反馈

# 5. 合并
git checkout main
git merge feature/user-auth
git push origin main

# 6. 清理
git branch -d feature/user-auth
git push origin --delete feature/user-auth
```

### Bug 修复流程

```bash
# 1. 创建修复分支
git checkout main
git checkout -b bugfix/login-error

# 2. 修复
git add .
git commit -m "fix(auth): handle login error"
git push origin bugfix/login-error

# 3. 创建 PR 并合并
# 同上
```

---

## 8. 质量检查清单

### 分支

- [ ] 正确的分支命名
- [ ] 合适的分支策略
- [ ] 及时清理分支

### 提交

- [ ] 遵循 Conventional Commits
- [ ] 原子提交
- [ ] 清晰的提交信息

### PR

- [ ] 合适的 PR 规模
- [ ] 完整的 PR 描述
- [ ] 通过代码审查

### 合并

- [ ] 选择合适的合并策略
- [ ] 合并前检查
- [ ] 保持主分支清洁

---

*本规范随 Git 最佳实践演进持续更新。最后更新: 2026-07-17*
