---
name: read
description: Ingest web/pdf into chunked cache, then outline/find/read by chunk ids to avoid full-text context overflow.
entry: python scripts/read_tool.py
---

# Read Skill

Use this skill for long-document reading with strict chunk-based access.

Args for `run_skill_entry("read", args)`:
- `--workspace /abs/path ingest --source "<url_or_local_path>"`
- `--workspace /abs/path outline --doc-id "<doc_id>"`
- `--workspace /abs/path find --doc-id "<doc_id>" --query "<keywords>"`
- `--workspace /abs/path read --doc-id "<doc_id>" --chunk-ids "3,7,8"`

Output:
- JSON payload on stdout
- cache files in `<workspace>/.read_cache/<doc_id>/`

Rules:
- Always call `ingest` before `outline/find/read`.
- Never put whole document into context; only use `find` + `read` selected chunks.
- `read` requires explicit chunk ids.
- Chunking/retrieval tuning parameters are internal defaults. Do not tune them in normal agent workflow.
