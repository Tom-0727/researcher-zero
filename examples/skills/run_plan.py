from core.skills.plan.scripts.plan_tool import apply_patch, parse_plan


def main() -> None:
    print("== 1) 解析计划 ==")
    plan_text = """<PLAN>
- 收集需求
- 设计方案
- 实现功能
</PLAN>
"""
    plan = parse_plan(plan_text)
    print("parsed:", plan)

    print("\n== 2) 修改步骤 ==")
    patch_modify = """<<<<<<< SEARCH
- 设计方案
=======
- 细化技术方案
>>>>>>> REPLACE
"""
    plan = apply_patch(plan, patch_modify)
    print("after modify:", plan)

    print("\n== 3) 删除步骤 ==")
    patch_delete = """<<<<<<< SEARCH
- 收集需求
=======
>>>>>>> REPLACE
"""
    plan = apply_patch(plan, patch_delete)
    print("after delete:", plan)

    print("\n== 4) 插入步骤（锚点替换） ==")
    patch_insert = """<<<<<<< SEARCH
- 细化技术方案
=======
- 细化技术方案
- 拆解任务
>>>>>>> REPLACE
"""
    plan = apply_patch(plan, patch_insert)
    print("after insert:", plan)

    print("\n== 5) 追加步骤 ==")
    patch_append = """<<<<<<< SEARCH
=======
- 验证结果
>>>>>>> REPLACE
"""
    plan = apply_patch(plan, patch_append)
    print("after append:", plan)


if __name__ == "__main__":
    main()
