from core.tools.skill_meta_toolkit import SkillToolkit


def main() -> None:
    toolkit = SkillToolkit(roots=["core/skills"], allow_run_entry=True)
    if "search" not in toolkit.skills:
        raise RuntimeError("未找到 search 技能")

    print("== 1) 列出可用 skills ==")
    print(toolkit.list_available_skills())

    print("\n== 2) 加载 search 技能说明 ==")
    print(toolkit.load_skill("search"))

    print("\n== 3) Semantic Scholar 搜索 ==")
    print(
        toolkit.run_skill_entry(
            "search",
            '--provider semantic_scholar --query "\"Large Language Models\" hallucination mitigation" --limit 3',
        )
    )

    print("\n== 4) arXiv 搜索 ==")
    print(
        toolkit.run_skill_entry(
            "search",
            '--provider arxiv --query "\"Attention Is All You Need\"" --limit 3',
        )
    )

    print("\n== 5) Tavily 通用搜索 ==")
    print(
        toolkit.run_skill_entry(
            "search",
            '--provider general --query "langgraph tutorial" --limit 3 --kwargs-json \'{"topic": "general"}\'',
        )
    )


if __name__ == "__main__":
    main()
