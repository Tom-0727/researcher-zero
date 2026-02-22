---
name: search
description: Run paper/web search to find learning materials.
entry: python scripts/search_tool.py
---

# Search Skill

Use this skill to execute search through one CLI entry.

Args for `run_skill_entry("search", entry_args)`:
- `--provider semantic_scholar --query "<keywords>" [--limit 5]`
- `--provider general --query "<query>" [--limit 5] [--kwargs-json "<JSON_OBJECT>"]`

Output:
- JSON payload on stdout
- includes provider/query and search results

Provider notes:
- `semantic_scholar`: keyword-based academic search
- `general`: Tavily web search

Entry Args examples:
- `--provider semantic_scholar --query "\"Large Language Models\" hallucination mitigation" --limit 5`
- `--provider general --query "latest benchmark for code llm" --limit 5`
