---
name: search
description: Run paper/web search via one entry (semantic_scholar/arxiv/general) and return JSON.
entry: python scripts/search_tool.py
---

# Search Skill

Use this skill to execute search through one CLI entry.

Args for `run_skill_entry("search", args)`:
- `--provider semantic_scholar --query "<keywords>" [--limit 5]`
- `--provider arxiv --query "<keywords>" [--limit 5]`
- `--provider general --query "<query>" [--limit 5] [--kwargs-json "<JSON_OBJECT>"]`

Output:
- JSON payload on stdout
- includes provider/query and search results

Provider notes:
- `semantic_scholar`: keyword-based academic search (optional env: `S2_API_KEY`)
- `arxiv`: arXiv literature search
- `general`: Tavily web search (required env: `TAVILY_API_KEY`)

Args examples:
- `--provider semantic_scholar --query "\"Large Language Models\" hallucination mitigation" --limit 5`
- `--provider arxiv --query "\"Attention Is All You Need\"" --limit 3`
- `--provider general --query "latest benchmark for code llm" --limit 5`
- `--provider general --query "langgraph tutorial" --kwargs-json "{\"topic\":\"general\",\"search_depth\":\"advanced\"}"`
