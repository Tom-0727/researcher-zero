from typing import Literal

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from core.services.learn.configuration import LearnConfig
from core.services.learn.context_loader import (
    build_plan_context_payload,
    resolve_workspace,
)
from core.services.learn.plan import (
    load_plan_items_from_file,
    run_plan_task,
    start_next_subtask,
    transition_plan_item_status,
)
from core.services.learn.react import react_subgraph
from core.services.learn.state import LearnState
from core.services.learn.summarize import (
    run_finalize_summary,
    run_subtask_summary,
)
from core.tools.skill_meta_toolkit import build_skill_capability


async def validate_input(
    state: LearnState,
    config: RunnableConfig,
) -> Command[Literal["build_plan_context"]]:
    """Validate required input fields and normalize workspace path."""
    task = state.get("task", "").strip()
    if not task:
        raise ValueError("task cannot be empty.")
    workspace = state.get("workspace", "").strip()
    if not workspace:
        raise ValueError("workspace cannot be empty.")

    resolved_workspace = str(resolve_workspace(workspace))
    return Command[Literal['build_plan_context']](
        goto="build_plan_context",
        update={
            "workspace": resolved_workspace,
            "task": task,
        },
    )


async def build_plan_context(
    state: LearnState,
    config: RunnableConfig,
) -> Command[Literal["plan_task"]]:
    """Load context + skill metadata and build one-time plan system prompt."""
    configurable = LearnConfig.from_runnable_config(config)
    capability = build_skill_capability(
        roots=configurable.skill_roots,
        allow_run_entry=True,
        command_timeout=configurable.skill_command_timeout,
    )
    payload = build_plan_context_payload(
        workspace=state["workspace"],
        task=state["task"],
        plan_file=state.get("plan_file", ""),
        skill_runtime_prompt=capability.prompt,
    )
    return Command(
        goto="plan_task",
        update={
            "workspace": payload["workspace"],
            "plan_file": payload["plan_file"],
            "system_prompt": payload["system_prompt"],
            "workspace_notes_summary": payload["workspace_notes_summary"],
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
            "read_doc_stage": {},
            "final_summary": "",
            "done": False,
        },
    )


async def plan_task(
    state: LearnState,
    config: RunnableConfig,
) -> Command[Literal["select_next_subtask"]]:
    """Run hardcoded plan workflow via pre-registered plan tools."""
    update = await run_plan_task(state=state, config=config)
    return Command(goto="select_next_subtask", update=update)


async def select_next_subtask(
    state: LearnState,
    config: RunnableConfig,
) -> Command[Literal["run_react_subgraph", "finalize_summary"]]:
    """Refresh plan snapshot and pick next todo item."""
    plan_items = load_plan_items_from_file(state["plan_file"])
    if any(item.status == "doing" for item in plan_items):
        raise ValueError("Plan contains 'doing' item before selecting next subtask.")

    picked_item, updated_items = start_next_subtask(state["plan_file"])
    if not picked_item:
        return Command(
            goto="finalize_summary",
            update={
                "plan_items": updated_items,
                "current_index": 0,
                "current_subtask_id": 0,
                "current_subtask": "",
            },
        )

    return Command(
        goto="run_react_subgraph",
        update={
            "plan_items": updated_items,
            "current_index": picked_item.id - 1,
            "current_subtask_id": picked_item.id,
            "current_subtask": picked_item.title,
            "react_messages": [],
            "react_turn": 0,
            "stop_reason": "",
            "read_doc_stage": {},
        },
    )


async def run_react_subgraph(
    state: LearnState,
    config: RunnableConfig,
) -> Command[Literal["summarize_subtask"]]:
    """Run react loop for current subtask."""
    updated_state = await react_subgraph.ainvoke(state, config=config)
    return Command(
        goto="summarize_subtask",
        update={
            "react_messages": updated_state.get("react_messages", []),
            "react_turn": updated_state.get("react_turn", 0),
            "stop_reason": updated_state.get("stop_reason", ""),
            "read_doc_stage": updated_state.get("read_doc_stage", {}),
        },
    )


async def summarize_subtask(
    state: LearnState,
    config: RunnableConfig,
) -> Command[Literal["select_next_subtask"]]:
    """Summarize current subtask and mark plan status done/aborted."""
    current_subtask_id = int(state.get("current_subtask_id", 0))
    if current_subtask_id <= 0:
        raise ValueError("current_subtask_id must be positive before summarize_subtask.")

    to_status: Literal["done", "aborted"] = (
        "aborted" if state.get("stop_reason", "") == "max_react_turns" else "done"
    )
    updated_plan_items = transition_plan_item_status(
        plan_file=state["plan_file"],
        item_id=current_subtask_id,
        to_status=to_status,
    )
    summary_update = await run_subtask_summary(state=state, config=config)
    return Command(
        goto="select_next_subtask",
        update={
            **summary_update,
            "plan_items": updated_plan_items,
        },
    )


async def finalize_summary(
    state: LearnState,
    config: RunnableConfig,
) -> Command[Literal["__end__"]]:
    """Generate final summary and finish graph."""
    plan_items = load_plan_items_from_file(state["plan_file"])
    if any(item.status in {"todo", "doing"} for item in plan_items):
        raise ValueError("Cannot finalize while plan still has todo/doing items.")

    summary_state = {**state, "plan_items": plan_items}
    summary_update = await run_finalize_summary(state=summary_state, config=config)
    return Command(
        goto=END,
        update={
            **summary_update,
            "plan_items": plan_items,
        },
    )


learn_graph = StateGraph(LearnState)
learn_graph.add_node("validate_input", validate_input)
learn_graph.add_node("build_plan_context", build_plan_context)
learn_graph.add_node("plan_task", plan_task)
learn_graph.add_node("select_next_subtask", select_next_subtask)
learn_graph.add_node("run_react_subgraph", run_react_subgraph)
learn_graph.add_node("summarize_subtask", summarize_subtask)
learn_graph.add_node("finalize_summary", finalize_summary)
learn_graph.add_edge(START, "validate_input")
learn_graph = learn_graph.compile()
