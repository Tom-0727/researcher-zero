from core.services.learn.state import PlanItem, SubtaskSummary


def get_plan_system_prompt(
    *,
    task: str,
    basic_info: str,
    taxonomy: str,
    network: str,
    main_challenge: str,
    workspace_notes: str,
    skill_runtime_prompt: str,
) -> str:
    """Build plan-stage system prompt with fixed context sections."""
    return f"""You are Learn Agent for continuous workspace knowledge accumulation.

Task goal:
{task}

Execution constraints:
1. Decompose task into independent, small, executable learning subtasks.
2. Do not output action scripts like "search first then summarize".
3. End planning by calling plan tools to write the canonical <PLAN> file.
4. Keep subtasks concise, avoid duplicates, and prioritize workspace knowledge gaps.

{skill_runtime_prompt}

<Basic_Info>
{basic_info}
</Basic_Info>

<Taxonomy>
{taxonomy}
</Taxonomy>

<Cognition_Network>
{network}
</Cognition_Network>

<Main_Challenge>
{main_challenge}
</Main_Challenge>

<Workspace_Notes_Summary>
{workspace_notes}
</Workspace_Notes_Summary>
"""


def get_plan_instruction(*, task: str, max_plan_steps: int) -> str:
    """Instruction for plan_task human message."""
    return f"""Please decompose the learning task into at most {max_plan_steps} subtasks.

Task:
{task}

Rules:
1. First think of subtask titles only.
2. Then call `plan_upsert_todos` once with JSON array:
   [{{"status":"todo","title":"..."}}]
3. Never include `id` in upsert payload.
4. If you need to remove duplicated steps, call `plan_remove_ids`.
"""


def render_plan_view(plan_items: list[PlanItem]) -> str:
    """Render plan items into compact text for follow-up prompts."""
    if not plan_items:
        return "<PLAN>\n</PLAN>"
    lines = [f"- [{item.status}][{item.id}] {item.title}" for item in plan_items]
    return "<PLAN>\n" + "\n".join(lines) + "\n</PLAN>"


def get_react_think_prompt(
    *,
    current_subtask_id: int,
    current_subtask: str,
    react_turn: int,
    max_react_turns: int,
) -> str:
    """Instruction text for one ReAct think turn."""
    return f"""Current subtask:
- id: {current_subtask_id}
- title: {current_subtask}
- turn: {react_turn}/{max_react_turns}

Rules:
1. Focus only on this subtask and ignore unrelated goals.
2. Choose exactly one next action: call one tool, or finish this subtask.
3. If evidence is enough, finish immediately instead of over-calling tools.
4. For long documents, only use `run_skill_entry("read", entry_args)` with strict order:
   ingest -> outline/find -> read(--chunk-ids).
5. Never put full document content into context; only keep selected chunk contents.
"""


def get_subtask_summary_prompt(*, current_subtask_id: int, current_subtask: str) -> str:
    """Instruction text for compressing one subtask trace."""
    return f"""Please summarize this finished subtask in concise Chinese.

Subtask:
- id: {current_subtask_id}
- title: {current_subtask}

Output format:
1. `结论`：1-3 句。
2. `证据`：最多 3 条要点（来源或工具结果）。
3. `沉淀`：写入/更新了哪些 workspace 文件；若没有写入，明确写“无”。
"""


def render_subtask_summaries(summaries: list[SubtaskSummary]) -> str:
    """Render subtask summaries for final aggregation prompt."""
    if not summaries:
        return "(none)"
    lines = [f"[{item.subtask_id}] {item.summary}" for item in summaries]
    return "\n".join(lines)


def get_final_summary_prompt(*, task: str, plan_view: str, summaries_view: str) -> str:
    """Instruction text for final learn report."""
    return f"""Please produce the final learn report in concise Chinese.

Original task:
{task}

Final plan snapshot:
{plan_view}

Subtask summaries:
{summaries_view}

Output sections:
1. `本次完成`：本轮学习实际完成内容。
2. `关键产出`：沉淀到 workspace 的可复用知识与文件。
3. `未完成与风险`：未完成项、阻塞点、已知不确定性。
"""
