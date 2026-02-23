---
name: read
description: Ingest web/pdf into chunked cache, then outline/find/read by chunk ids.
entry: python scripts/read_tool.py
---

# Read Skill

Use this skill for long-document reading with strict chunk-based access.

Args for `run_skill_entry("read", entry_args)`:
- `ingest --source "<url_or_local_path>"`
- `outline --doc-id "<doc_id>"`
- `read --doc-id "<doc_id>" --chunk-ids "3,7,8"`

Output:
- JSON payload on stdout
- cache files in `<repo_root>/cache/.read/<doc_id>/`

Rules:
- Always call `ingest` before `outline/find/read`.
- use `read` selected chunks and `read` requires explicit chunk ids.
