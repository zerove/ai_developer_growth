---
title: 数据库迁移策略
description: > 零停机、可回滚、版本化的 Schema 演进实践。
category: 工具层
tags: ['AI', 'Python', '测试', 'SQL', 'TypeScript']
difficulty: 基础
reading_time: 10 分钟
updated: 2026-07-21
---

# 数据库迁移策略

> 零停机、可回滚、版本化的 Schema 演进实践。

---

## 1. 核心原则

| 原则 | 说明 |
|------|------|
| **向后兼容** | 新代码必须能跑在旧 Schema 上（增量部署窗口期） |
| **幂等可重入** | 迁移脚本重复执行不报错、不破坏数据 |
| **显式回滚** | 每个迁移必须提供 `down` 逻辑或补偿方案 |
| **小步快跑** | 单次迁移 < 5 分钟，大表分批 |
| **版本化** | 迁移文件按版本号排序，Git 管理 |

---

## 2. 迁移工具对比

| 工具 | 语言 | 优点 | 缺点 | 适用 |
|------|------|------|------|------|
| **Alembic** | Python | SQLAlchemy 集成、自动生成、分支合并 | 学习曲线 | Python/SQLAlchemy 项目 |
| **Flyway** | Java/JVM | 企业级、回调、基线、云原生 | 需 JVM | Java/Kotlin、多语言团队 |
| **golang-migrate** | Go | 单二进制、嵌入式、CLI 友好 | 功能相对简单 | Go 项目 |
| **Prisma Migrate** | TypeScript | 声明式、类型安全、预览 | 较新、锁定 Prisma | TypeScript/Prisma 项目 |
| **Liquibase** | XML/YAML/SQL | 格式中立、回滚强、企业级 | XML 冗长 | 多语言、强合规团队 |

---

## 3. 迁移文件规范

```
migrations/
├── versions/
│   ├── 20260701_001_create_users_table.sql
│   ├── 20260702_002_add_email_index.sql
│   ├── 20260703_003_split_address_table.sql
│   └── ...
├── seeds/
│   └── 20260701_001_initial_roles.sql
└── env.py (Alembic) / flyway.conf
```

### 命名约定
```
{YYYYMMDD}_{序号}_{动词}_{对象}.sql
动词: create | add | drop | rename | alter | migrate | seed | fix
```

### 模板 (Alembic)
```python
# migrations/versions/20260720_004_add_user_version.py
"""Add optimistic lock version to users

Revision ID: 20260720_004
Revises: 20260719_003
Create Date: 2026-07-20 10:00:00
"""

from alembic import op
import sqlalchemy as sa

revision = "20260720_004"
down_revision = "20260719_003"
branch_labels = None
depends_on = None


def upgrade():
    # 1. 加列（可空，默认值）
    op.add_column("users", sa.Column("version", sa.Integer, nullable=True, server_default="1"))

    # 2. 回填现有数据（大表分批）
    op.execute("UPDATE users SET version = 1 WHERE version IS NULL")

    # 3. 设为非空
    op.alter_column("users", "version", nullable=False, server_default=None)

    # 4. 加索引（可选）
    op.create_index("ix_users_version", "users", ["version"])


def downgrade():
    op.drop_index("ix_users_version", table_name="users")
    op.drop_column("users", "version")
```

---

## 4. 零停机迁移模式

### 4.1 加列（安全）
```sql
-- ✅ 安全：新列可空、有默认值、不加锁（PG 11+）
ALTER TABLE users ADD COLUMN phone VARCHAR(20) DEFAULT '';
```

### 4.2 删列（双阶段）
```sql
-- 第 1 次部署：标记废弃，代码停止写入
ALTER TABLE users ALTER COLUMN phone DROP DEFAULT; -- 可选
-- 应用层：标记字段 @Deprecated，停止读写

-- 第 2 次部署（确认无读写）：真删
ALTER TABLE users DROP COLUMN phone;
```

### 4.3 重命名列（双写）
```sql
-- 1. 加新列
ALTER TABLE users ADD COLUMN full_name VARCHAR(100);

-- 2. 回填（大表分批）
UPDATE users SET full_name = CONCAT(first_name, ' ', last_name)
WHERE full_name IS NULL;

-- 3. 代码双写：写入 first_name/last_name 的同时写 full_name
--    读取优先 full_name，回退拼接

-- 4. 确认无旧代码读 first_name/last_name
ALTER TABLE users DROP COLUMN first_name;
ALTER TABLE users DROP COLUMN last_name;
```

### 4.4 修改类型（影子列）
```sql
-- 大表修改类型：加影子列 → 回填 → 切换 → 删旧
ALTER TABLE orders ADD COLUMN amount_new NUMERIC(12,2);
UPDATE orders SET amount_new = amount::numeric(12,2) WHERE amount_new IS NULL;
-- 代码切换读写 amount_new
ALTER TABLE orders RENAME COLUMN amount TO amount_old;
ALTER TABLE orders RENAME COLUMN amount_new TO amount;
-- 确认无问题后
ALTER TABLE orders DROP COLUMN amount_old;
```

### 4.5 大表加索引（并发）
```sql
-- PostgreSQL: CONCURRENTLY 不锁表
CREATE INDEX CONCURRENTLY idx_orders_user_created
ON orders (user_id, created_at DESC);

-- MySQL 8.0+: 算法 INPLACE
ALTER TABLE orders ADD INDEX idx_user_created (user_id, created_at), ALGORITHM=INPLACE, LOCK=NONE;
```

---

## 5. 大表数据迁移

### 分批回填模板
```python
def upgrade():
    batch_size = 10000
    offset = 0
    while True:
        result = op.execute(f"""
            UPDATE large_table
            SET new_col = compute(old_col)
            WHERE id IN (
                SELECT id FROM large_table
                WHERE new_col IS NULL
                ORDER BY id
                LIMIT {batch_size}
            )
        """)
        if result.rowcount == 0:
            break
        op.execute("COMMIT")  # 显式提交，释放锁
        # 可选：sleep 0.1s 降低主库压力
```

### 蓝绿表切换
```sql
-- 1. 建新表（同结构 + 新列/新类型）
CREATE TABLE users_new (LIKE users INCLUDING ALL);
ALTER TABLE users_new ADD COLUMN version INT DEFAULT 1;

-- 2. 双写触发器（或应用层双写）
CREATE TRIGGER sync_users_new
AFTER INSERT OR UPDATE ON users
FOR EACH ROW EXECUTE FUNCTION sync_to_new();

-- 3. 历史数据回填（分批、可中断）
INSERT INTO users_new SELECT *, 1 FROM users;

-- 4. 验证数据一致性
SELECT COUNT(*), SUM(CASE WHEN u.id IS NULL THEN 1 ELSE 0 END)
FROM users u FULL JOIN users_new n ON u.id = n.id;

-- 5. 切换（重命名、视图、或应用层切换）
BEGIN;
ALTER TABLE users RENAME TO users_old;
ALTER TABLE users_new RENAME TO users;
COMMIT;

-- 6. 观察期后清理
DROP TABLE users_old;
```

---

## 6. 回滚策略

| 场景 | 回滚方式 |
|------|----------|
| **加列/加索引** | `DROP COLUMN` / `DROP INDEX` (CONCURRENTLY) |
| **删列** | 从备份表恢复 / 重建列 + 从旧表回填 |
| **改类型** | 影子列回滚 / 从备份恢复 |
| **数据迁移** | 反向迁移脚本 / 标记列标识已迁移行 / 截断新表 |
| **结构性变更** | 蓝绿表重命名回滚 / `pg_basebackup` PITR |

> **原则**：回滚脚本随迁移同提交，CI 必须跑 `upgrade → downgrade → upgrade` 验证。

---

## 7. CI/CD 集成

```yaml
# .github/workflows/db-migrate.yml
jobs:
  migrate-check:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env: {POSTGRES_PASSWORD: test}
        ports: [5432:5432]
    steps:
      - uses: actions/checkout@v4
      - name: Run migrations up
        run: alembic upgrade head
      - name: Run migrations down
        run: alembic downgrade -1
      - name: Run migrations up again
        run: alembic upgrade head
      - name: Verify schema drift
        run: alembic check  # 确认无未生成迁移的模型变更

  deploy:
    needs: migrate-check
    if: github.ref == 'refs/heads/main'
    steps:
      - name: Deploy with migrations
        run: |
          # 蓝绿部署：先跑迁移，再切流量
          alembic upgrade head
          # 健康检查通过后切换流量
```

---

## 8. 常见坑清单

| 坑 | 后果 | 预防 |
|----|------|------|
| **无事务大表 DDL** | 锁表数小时 | `CONCURRENTLY`、分批、蓝绿表 |
| **外键未加索引** | 删父表死锁/全表扫描 | 显式 `CREATE INDEX ON child(parent_id)` |
| **枚举类型修改** | PG `ALTER TYPE` 锁表 | 新建类型、Cast、切换、删旧 |
| **隐式类型转换** | 索引失效、全表扫描 | 显式 `CAST`、列类型统一 |
| **迁移依赖顺序错** | 并行部署失败 | `depends_on` 显式声明分支依赖 |
| **生产直跑未测迁移** | 数据丢失/停机 | Staging 必跑、数据量模拟、回滚演练 |

---

## 9. 迁移检查清单

- [ ] 迁移文件命名规范、单一职责
- [ ] `upgrade` / `downgrade` 对称、可重入
- [ ] 大表操作：分批、CONCURRENTLY、蓝绿表
- [ ] 无破坏性变更（删列、改类型）未双阶段
- [ ] 外键有索引、枚举变更用影子类型
- [ ] CI 跑通 `up → down → up`、无 drift
- [ ] 文档记录：影响表、预计耗时、回滚步骤、负责人
- [ ] 部署窗口确认、值班人员、监控告警就绪

---

*迁移是数据库的 Git。最后更新: 2026-07-20*
