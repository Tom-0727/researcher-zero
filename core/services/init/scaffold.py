from __future__ import annotations

from pathlib import Path


TEMPLATES: dict[str, str] = {
    "Basic_Context/basic_info.md": """---
tags: [basic-context, definition]
---

# 基础定义

- 该领域是什么：
- 研究对象是什么：
- 研究边界是什么：
""",
    "Basic_Context/taxonomy.md": """---
tags: [basic-context, taxonomy]
---

# 分类网络

- Category：
- Concept：
- 层级关系：
""",
    "Cognition/main_challenge.md": """---
tags: [cognition, challenge]
---

# 核心挑战

- 当前未解决问题：
- 为什么难：
- 已有方案瓶颈：
""",
    "Cognition/network.md": """---
tags: [cognition, network]
---

# 关系网络

- 核心概念关联：
- 演化脉络：
- 关键转折点：
""",
    "Atomic_Knowledge/methods.md": """---
tags: [atomic-knowledge, methods]
---

# 方法与论文

- 方法名：
- 论文：
- 核心思路：
- 适用条件：
""",
    "Atomic_Knowledge/benchmarks.md": """---
tags: [atomic-knowledge, benchmarks]
---

# 评测指标

- 指标名：
- 衡量目标：
- 对应挑战：
- 局限性：
""",
    "Atomic_Knowledge/surveys.md": """---
tags: [atomic-knowledge, surveys]
---

# 综述与思想

- 观点：
- 分类方法：
- 抽象框架：
""",
    "Atomic_Knowledge/blogs.md": """---
tags: [atomic-knowledge, blogs]
---

# 网络文章

- 文章：
- 主要启发：
- 可信度评估：
""",
    "Alignment/human_preference.md": """---
tags: [alignment, human-preference]
---

# 人类偏好与负面约束

- 人类偏好：
- 禁忌/风险边界：
- 决策冲突处理原则：
""",
}


def init_research_workspace(output_dir: str | Path) -> list[Path]:
    """在指定目录下创建研究初始化文件，并返回实际写入的文件路径列表。"""
    base = Path(output_dir).expanduser().resolve()
    base.mkdir(parents=True, exist_ok=True)

    created_files: list[Path] = []
    for rel_path, content in TEMPLATES.items():
        target = base / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        created_files.append(target)
    return created_files
