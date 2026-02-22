import json
import re
from pathlib import Path
from typing import Any, Literal

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command

from core.services.learn.configuration import LearnConfig
from core.services.learn.context_loader import (
    build_learn_context_payload,
    resolve_workspace,
)
from core.services.learn.prompts import get_plan_instruction
from core.services.learn.state import LearnState, PlanItem
from core.skills.plan import build_plan_tools
from core.skills.plan.scripts.plan_tool import mutate_plan_file
from core.tools.skill_meta_toolkit import build_skill_capability

load_dotenv()
configurable_model = init_chat_model(
    configurable_fields=("model", "max_tokens", "temperature", "model_provider"),
)

PLAN_RE = re.compile(r"<PLAN>\s*(.*?)\s*</PLAN>", re.DOTALL)
PLAN_LINE_RE = re.compile(r"^- \[(todo|doing|done|aborted)\]\[(\d+)\] (.+)$")
STATUS_TRANSITIONS: dict[str, set[str]] = {
    "todo": {"doing"},
    "doing": {"done", "aborted"},
    "done": set(),
    "aborted": set(),
}


def parse_plan_items(source: str, *, from_file: bool = False) -> list[PlanItem]:
    """Parse <PLAN> block into plan items; ids by order. from_file=True: source is path."""
    text = Path(source).expanduser().resolve().read_text(encoding="utf-8") if from_file else source
    match = PLAN_RE.search(text)
    body = match.group(1).strip() if match else ""
    items: list[PlanItem] = []
    for raw in body.splitlines():
        m = PLAN_LINE_RE.fullmatch(raw.strip())
        if m and m.group(3).strip():
            items.append(PlanItem(id=len(items) + 1, title=m.group(3).strip(), status=m.group(1)))
    return items


def _find_item(plan_items: list[PlanItem], item_id: int) -> PlanItem:
    """Get one plan item by id with strict validation."""
    if item_id <= 0:
        raise ValueError(f"item_id must be positive, got {item_id}.")
    if item_id > len(plan_items):
        raise ValueError(
            f"item_id out of range: {item_id}. Current max id is {len(plan_items)}."
        )
    return plan_items[item_id - 1]


def transition_plan_item_status(
    *,
    plan_file: str,
    item_id: int,
    to_status: Literal["doing", "done", "aborted"],
) -> list[PlanItem]:
    """Transition one plan item status with strict runtime-owned rules."""
    current_items = parse_plan_items(plan_file, from_file=True)
    current_item = _find_item(current_items, item_id)
    if to_status not in STATUS_TRANSITIONS[current_item.status]:
        raise ValueError(
            f"Invalid status transition for id={item_id}: "
            f"{current_item.status} -> {to_status}."
        )

    payload = json.dumps(
        [
            {
                "id": item_id,
                "status": to_status,
                "title": current_item.title,
            }
        ],
        ensure_ascii=False,
    )
    updated_plan_text = mutate_plan_file(
        plan_path=str(Path(plan_file).expanduser().resolve()),
        op="upsert",
        items_json=payload,
        ids_csv=None,
    )
    updated_items = parse_plan_items(updated_plan_text)
    if updated_items[item_id - 1].status != to_status:
        raise RuntimeError(
            f"Failed to persist plan status transition id={item_id} -> {to_status}."
        )
    return updated_items


def pick_next_todo_item(plan_items: list[PlanItem]) -> PlanItem | None:
    """Return first todo item in plan order."""
    for item in plan_items:
        if item.status == "todo":
            return item
    return None


def start_next_subtask(plan_file: str) -> tuple[PlanItem | None, list[PlanItem]]:
    """Select first todo and transition it to doing."""
    current_items = parse_plan_items(plan_file, from_file=True)
    next_item = pick_next_todo_item(current_items)
    if not next_item:
        return None, current_items
    updated_items = transition_plan_item_status(
        plan_file=plan_file,
        item_id=next_item.id,
        to_status="doing",
    )
    return updated_items[next_item.id - 1], updated_items


def _invoke_tool(tool_obj: Any, tool_args: dict[str, Any]) -> str:
    """Execute one LangChain tool call and normalize output text."""
    payload = tool_obj.invoke(tool_args)
    if not isinstance(payload, str):
        return str(payload)
    return payload


async def plan_node(
    state: LearnState,
    config: RunnableConfig,
) -> Command[Literal["select_next_subtask"]]:
    """Build plan context, run plan generation, return full state update and next node."""
    task = state.get("task", "").strip()
    workspace = state.get("workspace", "").strip()
    resolved_workspace = str(resolve_workspace(workspace))

    configurable = LearnConfig.from_runnable_config(config)
    capability = build_skill_capability(
        roots=configurable.skill_roots,
        allow_run_entry=True,
        command_timeout=configurable.skill_command_timeout,
    )
    payload = build_learn_context_payload(
        workspace=resolved_workspace,
        task=task,
        plan_file=state.get("plan_file", ""),
    )
    planning_state = {
        **state,
        "workspace": payload["workspace"],
        "plan_file": payload["plan_file"],
        "system_prompt": payload["system_prompt"],
        "skill_runtime_prompt": capability.prompt,
        "available_skills": sorted(capability.toolkit.skills.keys()),
        "plan_items": [],
        "current_index": 0,
        "current_subtask_id": 0,
        "current_subtask": "",
        "subtask_summaries": [],
        "react_messages": [],
        "react_turn": 0,
        "stop_reason": "",
        "condensed_messages": [],
        "final_summary": "",
        "done": False,
    }

    plan_tools = [
        tool_obj
        for tool_obj in build_plan_tools(plan_file=planning_state["plan_file"])
        if tool_obj.name == "plan_upsert_todos"
    ]
    tool_map = {tool_obj.name: tool_obj for tool_obj in plan_tools}
    plan_model = (
        configurable_model
        .bind_tools(plan_tools, tool_choice="required")
        .with_config({
            "model": configurable.plan_model,
            "model_provider": "openai",
            "max_tokens": 400,
            "temperature": 0.1,
            "timeout": configurable.skill_command_timeout,
        })
    )
    messages = [
        SystemMessage(content=planning_state["system_prompt"]),
        HumanMessage(
            content=get_plan_instruction(
                task=planning_state["task"],
                max_plan_steps=configurable.max_plan_steps,
            )
        ),
    ]
    response = await plan_model.ainvoke(messages)
    if not response.tool_calls:
        raise ValueError("No plan tool call in plan node output.")

    tool_messages: list[ToolMessage] = []
    for tool_call in response.tool_calls:
        tool_name = tool_call.get("name", "")
        if tool_name != "plan_upsert_todos":
            raise ValueError(
                f"Plan stage only accepts `plan_upsert_todos`, got {tool_name!r}."
            )
        tool_args = tool_call.get("args", {}) or {}
        plan_text = _invoke_tool(tool_map[tool_name], tool_args)
        tool_call_id = tool_call.get("id")
        if not tool_call_id:
            raise ValueError("Missing tool_call id in model output.")
        tool_messages.append(
            ToolMessage(content=plan_text, tool_call_id=tool_call_id)
        )

    parsed_items = parse_plan_items(planning_state["plan_file"], from_file=True)[
        : configurable.max_plan_steps
    ]

    return Command(
        goto="select_next_subtask",
        update={
            **planning_state,
            "messages": [response, *tool_messages],
            "plan_items": parsed_items,
        },
    )
