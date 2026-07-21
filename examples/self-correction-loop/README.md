# Self-Correction Loop

> AI 代码质量保证：验证 → 重试 → 修正闭环。

---

## 定位

验证 `docs/efficiency/full-cycle-workflow` 中的"引导 → 生成 → 验证 → 修正"闭环方法论。

## 核心能力

| 组件 | 描述 |
|------|------|
| `CorrectionLoop` | 主循环：运行测试 → 失败时 AI 修复 → 重试 |
| `Strategies` | 修复策略：语法修复、类型修复、逻辑修复、测试驱动修复 |
| `Runner` | 测试运行器：支持 unittest / pytest |
| `Results` | 结果追踪：记录修正历史、成功率、尝试次数 |

### 修正流程

```
1. 运行测试
   ↓ (失败)
2. 获取错误信息
   ↓
3. AI 分析错误原因
   ↓
4. 生成修复方案
   ↓
5. 应用修复
   ↓
6. 回到步骤 1
   ↓ (成功或达到最大重试次数)
7. 返回最终结果
```

## 快速开始

```bash
pip install -e .

# 运行修正循环
python runner.py <target_file> --max-retries 5
```

## 测试

```bash
python -m pytest tests/ -v
```

## 相关文档

- [[docs/efficiency/full-cycle-workflow|全周期工作流]]
- [[docs/efficiency/automated-bugfix|自动化 Bug 修复]]
