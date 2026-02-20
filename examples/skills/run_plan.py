import json
from pathlib import Path
from tempfile import TemporaryDirectory

from core.skills.plan.scripts.plan_tool import mutate_plan_file


def main() -> None:
    with TemporaryDirectory(prefix="plan-skill-") as tmp_dir:
        plan_path = Path(tmp_dir) / "plan.md"

        print("== 1) 从无文件开始，批量初始化 ==")
        print(
            mutate_plan_file(
                plan_path=plan_path,
                op="upsert",
                items_json=json.dumps(
                    [
                        {"status": "todo", "title": "收集需求"},
                        {"status": "todo", "title": "设计方案"},
                        {"status": "todo", "title": "实现功能"},
                    ],
                    ensure_ascii=False,
                ),
                ids_csv=None,
            )
        )

        print("\n== 2) 批量 upsert：修改 + 追加 ==")
        print(
            mutate_plan_file(
                plan_path=plan_path,
                op="upsert",
                items_json=json.dumps(
                    [
                        {"id": 2, "status": "doing", "title": "细化技术方案"},
                        {"status": "todo", "title": "验证结果"},
                    ],
                    ensure_ascii=False,
                ),
                ids_csv=None,
            )
        )

        print("\n== 3) 批量 remove：删除多个 id，并自动重排 ==")
        print(
            mutate_plan_file(
                plan_path=plan_path,
                op="remove",
                items_json=None,
                ids_csv="1,3",
            )
        )

        print("\n== 4) 再次 upsert：按新动态 id 更新状态 ==")
        print(
            mutate_plan_file(
                plan_path=plan_path,
                op="upsert",
                items_json=json.dumps(
                    [
                        {"id": 1, "status": "done", "title": "细化技术方案"},
                        {"id": 2, "status": "doing", "title": "验证结果"},
                    ],
                    ensure_ascii=False,
                ),
                ids_csv=None,
            )
        )


if __name__ == "__main__":
    main()
