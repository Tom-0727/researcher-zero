---
name: plan
description: Apply SEARCH/REPLACE patch to a <PLAN> file. Input plan path + patch text, output updated plan content and persist to file.
entry: python scripts/plan_tool.py
---

# Plan Skill

This skill only provides one capability:

- Input: plan file path + patch text (SEARCH/REPLACE format)
- Output: patched `<PLAN>...</PLAN>` content
- Side effect: write patched content back to the same plan file (create file if missing)

## Output Rules For LLM

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

## Agent Execution

- `python scripts/plan_tool.py --plan /abs/path/plan.md --patch "<PATCH_TEXT>"`
