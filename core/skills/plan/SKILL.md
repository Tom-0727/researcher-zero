---
name: plan
description: Append todo steps to a <PLAN> file or remove steps by id. Agent should only do add/remove operations.
entry: python scripts/plan_tool.py
---

# Plan Skill

Use this skill only for plan structure edits:
- add new steps
- remove existing steps

Args for `run_skill_entry("plan", entry_args)`:
- `--plan /abs/path/plan.md --op upsert --items-json "<JSON_ARRAY>"`
- `--plan /abs/path/plan.md --op remove --ids "1,3,5"`

Output:
- updated `<PLAN>...</PLAN>` text
- write back to the same `--plan` file (canonical format)

Plan line format (read-only for Agent):

```text
- [status][id] title
```

Rules:
- `id` is dynamic sequence id (`1..N`) and is auto-reindexed after each write.
- For `upsert`, append only:
  - each item must be `{"status":"todo","title":"..."}`.
  - do not include `id`.
  - do not use `upsert` to modify existing items.
- For `remove`, you may delete one or more ids in one call.
- Do not change status (`todo/doing/done/aborted`) via this skill.

Args examples:
- Initialize plan with multiple steps:
  - `--plan /abs/path/plan.md --op upsert --items-json "[{\"status\":\"todo\",\"title\":\"分析 memory 核心维度\"},{\"status\":\"todo\",\"title\":\"调研代表性系统\"}]"`
- Append more steps:
  - `--plan /abs/path/plan.md --op upsert --items-json "[{\"status\":\"todo\",\"title\":\"提炼设计原则\"}]"`
- Batch remove:
  - `--plan /abs/path/plan.md --op remove --ids "2,4"`
