# ADR-031: test_rule_loader_file_hash 权限测试 root 跳过决策

## 状态
接受

## 日期
2026-09-02

## 背景

Phase 32 子任务 2a (ADR-030): 写 rule_loader.py `_file_hash` 测试。
测试覆盖 3 个分支时, 遇到**真实陷阱**:

- Linux 上, 即使 `chmod 0o000` 后, **root 用户 (uid=0)** 仍可读文件 (CAP_DAC_OVERRIDE capability)
- 但 chmod 的位运算容易出错: `S_IRWXU | S_IRWXG | S_IRWXO & ~S_IRUSR` 因 `&` 优先级低于 `|`, 实际是 `0o777 & ~0o444 = 0o333` (有写+执行权限, 没有读), 这正好是**反效果**(更宽松)
- 修复后: 用 `target.chmod(0o000)` 显式更安全

## 决策

### 决策 1: 跳过 root 用户的权限测试

```python
if os.geteuid() == 0:
    pytest.skip("root 用户可绕过文件权限, 无法触发 OSError")
```

理由: 不可绕过 root capability, 测试无效。CI 通常以非 root 用户跑 (如 `github-runner`),跳过是正确选择。

### 决策 2: 用 `chmod(0o000)` 替代位运算

```python
# 反例 (位运算陷阱)
target.chmod(stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO & ~stat.S_IRUSR & ~stat.S_IRGRP & ~stat.S_IROTH)
# 实际结果: 0o773 (可写+可执行, 但仍可读)

# 正例 (显式)
target.chmod(0o000)
```

理由: 位运算优先级陷阱, 显式八进制更安全 + 可读。

### 决策 3: 修后 cleanup 用 `chmod(0o644)` 而非 `stat.S_IRWXU | S_IRWXG | S_IRWXO`

理由: 同决策 2, 一致性 + 安全。

## 后果

### 正面
- 真实发现位运算陷阱 (可推广到其他测试)
- 跳过 root 测试避免误判
- 测试 6/6 通过

### 负面
- root 环境无法验证 OSError 兜底 (但 CI 通常非 root)
- 若未来需要 root 环境测试, 需用 mock (monkeypatch _file_hash 内部 read_bytes)

## 验证

- pytest: 6/6 passed ✅
- ruff: clean ✅
- 覆盖率: rule_loader.py 14% (只覆盖 _file_hash 9 行, Phase 32 子任务 2a 完成)
- 总覆盖率未变 (测试仅覆盖9/274 行, 总体增益微小)

## 后续

- Phase 32 子任务 2b (`_disk_cache` 系列) 继续
- Phase 32 子任务 2c-2e 按 ADR-030 排序