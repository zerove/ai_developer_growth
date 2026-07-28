# 规则加载架构

## 两条加载路径

```
YAML 规则文件                       Python 硬编码规则
(ai-dev-framework/languages/)       (tools/scripts/rules_engine/)
         │                                    │
         ▼                                    ▼
rule_loader.py ─── merge ───► security_patterns.py
         │                                    │
         └────────────┬───────────────────────┘
                      ▼
         load_rules_for_language()
                      │
                      ▼
              anti_pattern_checker.py
              naming_checker.py
              complexity_checker.py
```

### 路径 1: YAML 文件（声明式）

- 位置: `ai-dev-framework/languages/{lang}/rules.d/anti_patterns.yml`
- 格式: YAML，含 `anti_patterns`、`naming`、`thresholds` 三节
- 加载: `rule_loader.load_rules()` → 内存缓存 + 磁盘缓存
- 合并: 语言规则 + 框架规则 + 通用安全规则

### 路径 2: Python 硬编码（命令式）

- 位置: `tools/scripts/rules_engine/security_patterns.py`
- 内容: 跨语言安全模式（SQL注入、密码硬编码等）
- 加载: `get_security_rules()` → 直接返回 Python dict
- 合并: 通过 `rule_loader.load_rules_for_language()` 统一 merge

### 自定义规则覆盖

优先级（高→低）：
1. `~/.config/adg/rules.yml`（用户全局）
2. `.adg/rules.yml`（项目级）
3. `.ai-rules/*.yml`（旧版目录级）
4. YAML 语言规则（框架内置）
5. Python 安全模式（引擎内置）

## 设计说明

两条路径有意共存：
- YAML 路径适合管理大量声明式规则（目前 26 语言 × ~10 规则 = 260+）
- Python 路径适合实现需要逻辑判断的跨语言安全模式
- 自定义覆盖在加载时按优先级 merge，不修改源文件
