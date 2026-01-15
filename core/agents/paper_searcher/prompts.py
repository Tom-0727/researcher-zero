from typing import List

from core.agents.paper_searcher.state import PaperResult


def get_system_prompt() -> str:
    return "You are a focused academic paper searcher."


def get_paper_searcher_think_prompt(
    paper_search_task: str,
    history_queries: List[str],
    history_search_results: List[PaperResult],
) -> str:
    normalized_task = paper_search_task.strip()
    if not normalized_task:
        raise ValueError("paper_search_task cannot be empty")

    history_queries_prompt = ""
    if history_queries:
        history_queries_prompt = f"""<History Queries>
{history_queries}
</History Queries>
"""

    history_results_prompt = "None"
    if history_search_results:
        lines: List[str] = []
        for paper in history_search_results:
            abstract = paper.abstract[:800]
            lines.append(
                "Title: {title}\nYear: {year}\nCitations: {citations}\n"
                "Abstract: {abstract}".format(
                    title=paper.title,
                    year=paper.year or "n/a",
                    citations=paper.citations,
                    abstract=abstract,
                )
            )
        history_results_prompt = "\n\n".join(lines)

    return f"""<Task>
Decide the next Semantic Scholar search query, or finish the search.
</Task>

{history_queries_prompt}

<History Search Results>
{history_results_prompt}
</History Search Results>

<Information Seeking Task>
{normalized_task}
</Information Seeking Task>

<Instructions>
1. Output exactly one tool call: search_semantic_scholar or SearchComplete.
2. For search_semantic_scholar, provide ONE keyword-based query.
3. Use double quotes for exact phrases or paper titles.
4. Avoid repeating any previous queries.
5. Stop when you believe the task is sufficiently covered.
</Instructions>
"""
