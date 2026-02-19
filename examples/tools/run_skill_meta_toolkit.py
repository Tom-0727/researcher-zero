from pathlib import Path
import shlex

from core.tools.skill_meta_toolkit import SkillToolkit


def build_entry_args(plan_path: Path, patch_text: str) -> str:
    """组装 run_skill_entry 所需参数。"""
    return f"--plan {shlex.quote(str(plan_path))} --patch {shlex.quote(patch_text)}"


def run_plan_patch(toolkit: SkillToolkit, plan_path: Path, patch_text: str) -> str:
    """执行 plan skill patch 操作。"""
    return toolkit.run_skill_entry("plan", build_entry_args(plan_path, patch_text))


def main() -> None:
    """仅演示 plan skill 的创建与修改。"""
    toolkit = SkillToolkit(roots=["core/skills"], allow_run_entry=True)
    if "plan" not in toolkit.skills:
        raise RuntimeError("未找到 plan 技能")

    plan_path = Path("/Users/tom/Codes/researcher-zero/cache/plan_skill_demo.md")

    print("== 1) 创建计划 ==")
    # 空 SEARCH 表示追加，用于从空计划创建初始步骤。
    create_patch = """<<<<<<< SEARCH
=======
- 收集需求
- 设计方案
>>>>>>> REPLACE
"""
    print(run_plan_patch(toolkit, plan_path, create_patch))

    print("\n== 2) 修改计划 ==")
    modify_patch = """<<<<<<< SEARCH
- 设计方案
=======
- 细化技术方案
>>>>>>> REPLACE
"""
    print(run_plan_patch(toolkit, plan_path, modify_patch))


if __name__ == "__main__":
    main()
