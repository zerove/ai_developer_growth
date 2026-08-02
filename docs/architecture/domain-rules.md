---
title: "领域规则包模板"
description: "每个领域规则包是一个 YAML 文件,存放在 ai-dev-framework/doma..."
category: 工具层
tags: ['领域规则包模板', '差距', '的解决方案', '预设常见领域的特殊规则包', '设计', '每个领域规则包是一个']
difficulty: 基础
---

# 领域规则包模板

> 差距 6 的解决方案。预设常见领域的特殊规则包。

---

## 设计

每个领域规则包是一个 YAML 文件,存放在 `ai-dev-framework/domains/` 目录下。
用户通过 `.adg/config.yml` 启用:

```yaml
domains:
  - finance  # 启用金融规则
  - hipaa    # 启医疗规则
```

## 金融领域 (finance.yml)

```yaml
# 金融领域规则 — 交易系统、支付、账务

anti_patterns:
  - id: finance-float-money
    name: Floating point for money
    severity: error
    category: domain
    pattern: 'float|double.*(?:price|amount|money|balance|total|fee|rate)'
    message: 金额必须使用定点数或 decimal,不能使用浮点数
    fix_hint: Use Decimal or integer cents representation

  - id: finance-no-audit
    name: Missing audit log
    severity: error
    category: domain
    pattern: '(?:transfer|payment|refund|settle)'
    message: 资金变动操作必须记录审计日志
    fix_hint: Add audit trail entry for all financial transactions

  - id: finance-round-error
    name: Rounding without strategy
    severity: warning
    category: domain
    pattern: 'round\s*\(.*(?:amount|money|price|total|tax)'
    message: 金额舍入必须指定舍入模式 (HALF_UP/DOWN/EVEN)
    fix_hint: Specify RoundingMode and document the business rationale
```

## 医疗领域 (hipaa.yml)

```yaml
# 医疗/健康数据领域规则 — HIPAA 合规

anti_patterns:
  - id: health-phi-log
    name: PHI/PII data in logs
    severity: error
    category: domain
    pattern: 'log.*(?:ssn|patient|diagnosis|treatment|medical)'
    message: 受保护健康信息 (PHI) 不得出现在日志中
    fix_hint: Filter or mask PHI data before logging

  - id: health-unencrypted-pii
    name: Unencrypted PII storage
    severity: error
    category: domain
    pattern: '(?:patient|ssn|health|medical)_?\s*=\s*["''][^"'']+["'']'
    message: 个人身份信息 (PII) 必须加密存储
    fix_hint: Use field-level encryption for all PII data
```

## 游戏领域 (gaming.yml)

```yaml
# 游戏开发领域规则 — 性能敏感、帧率关键

anti_patterns:
  - id: game-alloc-in-hotpath
    name: Allocation in update loop
    severity: error
    category: domain
    pattern: '(?:Update|FixedUpdate|LateUpdate).*\bnew\b'
    message: Update 循环中的内存分配会导致 GC 暂停
    fix_hint: Pre-allocate in Awake/Start or use object pool

  - id: game-string-concat
    name: String concat in hot path
    severity: warning
    category: domain
    pattern: '(?:Update|FixedUpdate).*["'']\s*\+'
    message: Update 循环中的字符串拼接产生垃圾
    fix_hint: Use StringBuilder or pre-compute strings
```

## 集成方式

领域规则包在 `rule_loader.py` 中加载：

```python
def load_domain_rules(project_path: Path) -> dict:
    """从 .adg/config.yml 读取启用的领域，加载对应的规则包。"""
    config = load_project_config(project_path)
    domains = config.get("domains", [])
    rules = {"anti_patterns": []}
    for domain in domains:
        p = FRAMEWORK_DIR / "domains" / f"{domain}.yml"
        if p.exists():
            data = yaml.safe_load(p.read_text())
            rules["anti_patterns"].extend(data.get("anti_patterns", []))
    return rules
```
