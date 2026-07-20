# Python 示例项目

这是一个最小化的 Python 示例项目，展示如何使用 ai-dev-framework。

---

## 项目结构

```
python-example/
├── src/
│   └── main.py           # 主模块
├── tests/
│   └── test_main.py      # 测试文件
├── CLAUDE.md             # 项目规范
├── AGENTS.md             # Agent 索引
├── CONTEXT.md            # 项目上下文
└── pyproject.toml        # 项目配置
```

---

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 运行测试
pytest tests/ -v

# 代码检查
ruff check .
```

---

## Agent 示例

### main.py

```python
"""主模块"""


def add(a: int, b: int) -> int:
    """两个数相加。
    
    Args:
        a: 第一个数
        b: 第二个数
        
    Returns:
        两数之和
    """
    return a + b
```

### test_main.py

```python
"""测试文件"""

from src.main import add


def test_add_success():
    """测试加法成功"""
    assert add(1, 2) == 3


def test_add_negative():
    """测试负数"""
    assert add(-1, 1) == 0
```

---

## 质量门禁检查

```bash
# 检查代码质量
bash .ai-framework/quality-gates/scripts/check.sh python
```

---

*这是一个最小化的 Python 示例项目。*
