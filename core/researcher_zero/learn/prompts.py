from typing import Sequence

from core.researcher_zero.learn.state import PlanItem, SubtaskSummary


def get_plan_system_prompt(
    task: str,
    basic_info: str,
    taxonomy: str,
    network: str,
    main_challenge: str,
    max_plan_steps: int,
) -> str:
    """Build one-shot system prompt for task decomposition planning."""
    normalized_task = task.strip()
    if not normalized_task:
        raise ValueError("task cannot be empty")
    if max_plan_steps <= 0:
        raise ValueError("max_plan_steps must be positive")

    return f"""You are the Learn Agent for structured research planning.

<Goal>
Decompose the learning task into independent and executable subtasks.
</Goal>

<Task>
{normalized_task}
</Task>

<Basic Context>
{basic_info}
</Basic Context>

<Taxonomy>
{taxonomy}
</Taxonomy>

<Cognition Network>
{network}
</Cognition Network>

<Main Challenge>
{main_challenge}
</Main Challenge>

<Rules>
1. Produce task decomposition only, not tool/action scripts.
2. Each step must be smaller, independent, and executable.
3. Do not output "first search then summarize" style instructions.
4. Limit plan length to at most {max_plan_steps} items.
5. Output must strictly follow:
<PLAN>
- step 1
- step 2
</PLAN>
</Rules>
"""


def get_react_think_prompt(
    current_subtask: str,
    turn: int,
    max_turns: int,
) -> str:
    """Build instruction text for one ReAct think turn.

    Note: plan/history messages are assembled by reactor nodes, not here.
    """
    normalized_subtask = current_subtask.strip()
    if not normalized_subtask:
        raise ValueError("current_subtask cannot be empty")
    if turn <= 0:
        raise ValueError("turn must be positive")
    if max_turns <= 0:
        raise ValueError("max_turns must be positive")

    return f"""<Current Subtask>
{normalized_subtask}
</Current Subtask>

<Turn>
{turn}/{max_turns}
</Turn>

<Instructions>
Decide the single best next action for this subtask.
If the subtask is sufficiently completed, choose finish.
Output exactly one tool call.
</Instructions>
"""


def get_subtask_summary_prompt(
    subtask_id: str,
    current_subtask: str,
    react_trace_text: str,
) -> str:
    """Build instruction text for compressing one subtask trace."""
    normalized_subtask = current_subtask.strip()
    normalized_id = subtask_id.strip()
    normalized_trace = react_trace_text.strip()
    if not normalized_subtask:
        raise ValueError("current_subtask cannot be empty")
    if not normalized_id:
        raise ValueError("subtask_id cannot be empty")
    if not normalized_trace:
        raise ValueError("react_trace_text cannot be empty")

    return f"""<Subtask ID>
{normalized_id}
</Subtask ID>

<Subtask>
{normalized_subtask}
</Subtask>

<ReAct Trace>
{normalized_trace}
</ReAct Trace>

<Output Requirement>
Return only one concise paragraph as the subtask summary.
</Output Requirement>
"""


def get_final_summary_prompt(
    task: str,
    plan_items: Sequence[PlanItem],
    subtask_summaries: Sequence[SubtaskSummary],
) -> str:
    """Build prompt to produce final learn report."""
    normalized_task = task.strip()
    if not normalized_task:
        raise ValueError("task cannot be empty")

    plan_text = "None"
    if plan_items:
        plan_text = "\n".join(
            f"- [{item.status}] ({item.id}) {item.title}"
            for item in plan_items
        )

    summaries_text = "None"
    if subtask_summaries:
        summaries_text = "\n".join(
            f"- ({item.subtask_id}) {item.summary}"
            for item in subtask_summaries
        )

    return f"""<Task>
{normalized_task}
</Task>

<Final Plan Status>
{plan_text}
</Final Plan Status>

<Subtask Summaries>
{summaries_text}
</Subtask Summaries>

<Instructions>
Provide a final report that clearly states:
1) what was completed,
2) what outputs were produced,
3) what remains unfinished.
</Instructions>
"""
