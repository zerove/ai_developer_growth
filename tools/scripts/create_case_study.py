#!/usr/bin/env python3
"""
案例研究目录结构生成器
创建标准化的案例研究目录结构
"""

import argparse
from datetime import datetime
from pathlib import Path


def create_case_study_structure(name: str, base_dir: Path = Path("case-studies")) -> Path:
    """创建案例研究标准目录结构"""
    case_dir = base_dir / name.lower().replace(" ", "-")
    case_dir.mkdir(parents=True, exist_ok=True)

    # 创建标准子目录
    (case_dir / "code").mkdir(exist_ok=True)
    (case_dir / "docs").mkdir(exist_ok=True)
    (case_dir / "tests").mkdir(exist_ok=True)
    (case_dir / "assets").mkdir(exist_ok=True)  # 图表、截图等

    # 从模板生成 README.md
    template_path = Path("templates/case-study-template.md")
    if template_path.exists():
        template = template_path.read_text(encoding="utf-8")
    else:
        template = get_default_template()

    # 替换占位符
    title = name
    date = datetime.now().strftime("%Y-%m-%d")
    content = template.replace("[简短标题", title).replace("2026-07-21", date)

    readme_path = case_dir / "README.md"
    readme_path.write_text(content, encoding="utf-8")

    # 创建基础文档占位符
    for doc in ["PRD.md", "DESIGN.md", "RETROSPECTIVE.md"]:
        doc_path = case_dir / "docs" / doc
        if not doc_path.exists():
            doc_path.write_text(f"# {doc}\n\n待填写...\n", encoding="utf-8")

    # 创建 .gitkeep 确保空目录被跟踪
    for subdir in ["code", "tests", "assets"]:
        (case_dir / subdir / ".gitkeep").touch()

    print(f"✅ 创建案例研究目录: {case_dir}")
    print("   ├── README.md (从模板生成)")
    print("   ├── docs/")
    print("   │   ├── PRD.md")
    print("   │   ├── DESIGN.md")
    print("   │   └── RETROSPECTIVE.md")
    print("   ├── code/")
    print("   ├── tests/")
    print("   └── assets/")

    return case_dir


def get_default_template() -> str:
    """默认模板内容"""
    return """# 案例: [简短标题]

> **效率提升**: Nx | **项目类型**: [类型] | **AI 工具栈**: [工具栈]

---

## 背景

- **项目类型**: [CLI工具 / Web应用 / 后端API / 数据管道 / 遗留重构 / ...]
- **挑战**: [核心难点描述]
- **约束**: [技术栈/时间/团队/安全等限制]

---

## AI 协作过程

### 阶段 1: 需求分析 & PRD (传统 Xh → AI Ymin)
| 角色 | 动作 |
|------|------|
| **人** | [定义用户故事、验收标准、非功能需求] |
| **AI** | [生成 PRD.md、数据模型、API契约] |
| **验证** | [人工审查业务逻辑正确性] |

### 阶段 2: 架构设计 & 契约定义 (传统 Xh → AI Ymin)
| 角色 | 动作 |
|------|------|
| **人** | [确定技术栈、分层架构、接口契约] |
| **AI** | [生成模块结构、核心接口、错误处理规范] |
| **验证** | [架构守卫检查、接口一致性测试] |

### 阶段 3: 迭代编码 (TDD 循环) (传统 Xh → AI Ymin)
| 循环 | 测试先行 | 实现 | 验证 | 关键挑战 |
|------|----------|------|------|----------|
| 1 | [测试描述] | [实现描述] | ✅/❌ | [挑战描述] |
| 2 | [测试描述] | [实现描述] | ✅/❌ | [挑战描述] |

### 阶段 4: 优化 & 交付 (传统 Xh → AI Ymin)
| 角色 | 动作 |
|------|------|
| **人** | [性能测试、文档审查、发布检查] |
| **AI** | [生成README、测试补全、优化建议] |
| **最终验收** | [覆盖率 X%、测试通过、端到端验证] |

---

## 效率对比

| 阶段 | 传统方式 | AI 协作 | 提升 | 备注 |
|------|----------|---------|------|------|
| 需求分析 & PRD | X 小时 | Y 分钟 | Nx |  |
| 架构设计 & 契约 | X 小时 | Y 分钟 | Nx |  |
| 核心编码 & TDD | X 小时 | Y 分钟 | Nx |  |
| 调试 & 修复 | X 小时 | Y 分钟 | Nx |  |
| 文档 & 交付 | X 小时 | Y 分钟 | Nx |  |
| **总计** | **X 小时** | **~Y 分钟** | **Nx** |  |

---

## 关键洞察

1. **洞察 1**: [可直接复用的技巧/模式/原则]
2. **洞察 2**: [可直接复用的技巧/模式/原则]
3. **洞察 3**: [可直接复用的技巧/模式/原则]
4. **洞察 4** (可选):
5. **洞察 5** (可选):

---

## 适用场景

- [ ] 个人开发者
- [ ] 小团队 (2-5 人)
- [ ] 中大型团队 (5+ 人)
- [ ] 遗留系统重构
- [ ] 从 0 到 1 新项目
- [ ] API/后端开发
- [ ] 前端/UI 开发
- [ ] 数据/ML 管道
- [ ] DevOps/基础设施

---

## 交付物清单

- [ ] `docs/PRD.md` - 产品需求文档
- [ ] `docs/DESIGN.md` - 架构设计文档
- [ ] 核心代码 (已开源或可公开关键片段)
- [ ] 单元测试 (覆盖率 > 80%)
- [ ] 效率对比数据 (量化)
- [ ] 关键洞察总结
- [ ] 适用场景标注

---

## 提交前检查

- [ ] 标题格式: `[Case Study] 简短标题`
- [ ] Label: `case-study` + `needs-review`
- [ ] 必填章节完整 (背景/过程/对比/洞察/场景/清单)
- [ ] 效率数据量化 (含总计行)
- [ ] 关键洞察 ≥ 3 条，可复用
- [ ] 代码/文档链接有效

---

## 导航

- [[MOC|返回知识地图]]
- [[docs/efficiency/full-cycle-workflow|全周期工作流方法论]]

---

*最后更新: 2026-07-21*
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="创建标准化案例研究目录结构")
    parser.add_argument("name", help="案例研究名称 (如: 'AI 驱动的 API 网关开发')")
    parser.add_argument("--dir", default="case-studies", help="基础目录 (默认: case-studies)")
    args = parser.parse_args()

    base = Path(args.dir)
    case_dir = create_case_study_structure(args.name, base)

    print("\n📋 下一步:")
    print(f"1. 编辑 {case_dir}/README.md 填入实际内容")
    print(f"2. 在 {case_dir}/docs/ 完善 PRD.md 和 DESIGN.md")
    print(f"3. 将代码放入 {case_dir}/code/")
    print("4. 提交 PR，参考 CONTRIBUTING.md 案例提交流程")


if __name__ == "__main__":
    main()
