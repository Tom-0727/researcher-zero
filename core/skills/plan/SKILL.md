---
name: plan
description: Structured planning and deterministic plan edits for agents. Use when the agent needs to create a plan list from model output, or update an existing plan via SEARCH/REPLACE-style patches (insert, delete, modify, append).
---

# Plan Skill

Use `scripts/plan_tool.py` as the single parser/editor.

## Output Rules For LLM

Always output plan text in this exact format:

```text
<PLAN>
- First step
- Second step
</PLAN>
```

Always output plan patch text in this exact format (one or more blocks):

```text
<<<<<<< SEARCH
- line(s) to find in current plan
=======
- replacement line(s)
>>>>>>> REPLACE
```

Use patch blocks for operations:

- Modify: set `SEARCH` to old line(s), `REPLACE` to new line(s).
- Delete: set `SEARCH` to line(s), keep `REPLACE` empty.
- Insert: set `SEARCH` to anchor line, set `REPLACE` to `anchor + new line(s)` (or `new line(s) + anchor`).
- Append: keep `SEARCH` empty, set `REPLACE` to new line(s).

## Script API

- `parse_plan(text: str) -> list[str]`
- `apply_patch(plan: list[str], patch_text: str) -> list[str]`

## CLI

- Parse from file: `python core/skills/plan/scripts/plan_tool.py parse plan.txt`
- Parse from stdin: `python core/skills/plan/scripts/plan_tool.py parse -`
- Patch: `python core/skills/plan/scripts/plan_tool.py patch --plan plan.txt --patch patch.txt`
