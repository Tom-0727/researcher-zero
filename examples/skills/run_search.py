import json
import shlex

from core.tools.skill_meta_toolkit import SkillToolkit


def build_entry_args(
    provider: str,
    query: str,
    limit: int = 5,
    kwargs_json: dict | None = None,
) -> str:
    """组装 run_skill_entry("search", args) 的参数字符串。"""
    parts = ["--provider", provider, "--query", query, "--limit", str(limit)]
    if kwargs_json is not None:
        parts.extend(["--kwargs-json", json.dumps(kwargs_json, ensure_ascii=False)])
    return " ".join(shlex.quote(item) for item in parts)


def run_search_entry(
    toolkit: SkillToolkit,
    provider: str,
    query: str,
    limit: int = 5,
    kwargs_json: dict | None = None,
) -> str:
    """执行 search skill 的一次 entry 调用。"""
    args = build_entry_args(
        provider=provider,
        query=query,
        limit=limit,
        kwargs_json=kwargs_json,
    )
    return toolkit.run_skill_entry("search", args)


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
        run_search_entry(
            toolkit=toolkit,
            provider="semantic_scholar",
            query='"Large Language Models" hallucination mitigation',
            limit=3,
        )
    )

    print("\n== 4) arXiv 搜索 ==")
    print(
        run_search_entry(
            toolkit=toolkit,
            provider="arxiv",
            query='"Attention Is All You Need"',
            limit=3,
        )
    )

    print("\n== 5) Tavily 通用搜索 ==")
    print(
        run_search_entry(
            toolkit=toolkit,
            provider="general",
            query="langgraph tutorial",
            limit=3,
            kwargs_json={"topic": "general"},
        )
    )


if __name__ == "__main__":
    main()
