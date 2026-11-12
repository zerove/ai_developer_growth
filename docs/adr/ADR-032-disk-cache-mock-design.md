# ADR-032: Phase 32 子任务 2b disk_cache mock 设计决策

## 状态
接受

## 日期
2026-09-02

## 背景

按 ADR-030 启动 Phase 32 子任务 2b: 覆盖 `_load_disk_cache` + `_save_disk_cache`。
这两个函数引用模块级硬编码常量 `_DISK_CACHE_FILE` 和 `_DISK_CACHE_DIR`, 测试时**不能写真实路径**, 否则污染 `.cache/rules_engine/rules_cache.json`。

## 决策

### 决策 1: monkeypatch 模块级常量 (而非改源码)

```python
@pytest.fixture
def tmp_cache_path(tmp_path, monkeypatch):
    cache_dir = tmp_path / ".cache" / "rules_engine"
    cache_file = cache_dir / "rules_cache.json"
    monkeypatch.setattr(rule_loader, "_DISK_CACHE_DIR", cache_dir)
    monkeypatch.setattr(rule_loader, "_DISK_CACHE_FILE", cache_file)
    return cache_file
```

理由:
- 不改源码 (避免侵入式重构)
- pytest 内置 fixture 自动清理 (monkeypatch.setattr 在 fixture 结束时还原)
- 简单清晰,无副作用

### 决策 2: 覆盖 7 个分支 (而非 4 个)

原 ADR-030 估时 4 分支,实际实施发现需 7 分支:
- `_load_disk_cache`:
 - 文件不存在 → `{}`
 - 正常 JSON → dict
 - JSONDecodeError (语法错) → `{}`
 - 空文件 → `{}` (JSONDecodeError 兜底)
 - OSError (权限拒绝) → `{}` (root 跳过, ADR-031)
- `_save_disk_cache`:
 - mkdir + write → 成功
 - 覆盖现有 → 成功
 - OSError (权限拒绝 mkdir) → 静默忽略 (root 跳过, ADR-031)

### 决策 3: 测试不污染真实缓存

`tmp_path` pytest fixture 自动创建隔离目录, 测试结束自动清理。
即使 `monkeypatch` 失败, 真实路径未被触及 (因为常量被临时替换)。

### 决策 4: 不解决"文件不存在但目录不存在"的混合情况

当前测试覆盖:
- 文件不存在 (目录可能存在)
- 文件存在 + JSON 合法
- 文件存在 + JSON 不合法
- 文件存在 + 空
- 文件存在 + OSError

未覆盖:
- 目录不存在 + 读 (由 `not _DISK_CACHE_FILE.exists()` 跳过, 实际不可能)
- 目录不存在 + 写 (由 `mkdir parents=True exist_ok=True` 处理)

理由: 这些路径在实际代码中已合并, 测试已通过 mkdir 间接覆盖。

## 后果

### 正面
- 8 个测试覆盖磁盘缓存完整生命周期
- 不污染真实缓存目录
- mock 设计可复用到 Phase 32 子任务 2c (LRU cache)

### 负面
- rule_loader.py 覆盖率 14% → 18% (+4pp), 仍远低于 80% 门禁
- 后续 2c/2d/2e 累计估时 5h (单文件覆盖)

## 验证

- pytest: 8/8 passed ✅
- ruff: clean ✅
- 覆盖率: rule_loader.py **18%** (子任务 2b 完成)
- 测试套件 3709 → 3717 (+8)

## 后续

- Phase 32 子任务 2c: `_rules_hash_cached` LRU cache (1h)
- Phase 32 子任务 2d: yaml 加载 (2h)
- Phase 32 子任务 2e: 公开 API (2h)
