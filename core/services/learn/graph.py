from typing import Literal

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from core.services.learn.plan import (
    parse_plan_items,
    plan_node,
    start_next_subtask,
    transition_plan_item_status,
)
from core.services.learn.react import react_subgraph
from core.services.learn.state import LearnState
from core.services.learn.summarize import (
    run_finalize_summary,
    run_subtask_summary,
)


async def select_next_subtask(
    state: LearnState,
    config: RunnableConfig,
) -> Command[Literal["run_react_subgraph", "finalize_summary"]]:
    """Refresh plan snapshot and pick next todo item."""
    plan_items = parse_plan_items(state["plan_file"], from_file=True)
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
    plan_items = parse_plan_items(state["plan_file"], from_file=True)
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
learn_graph.add_node("plan_node", plan_node)
learn_graph.add_node("select_next_subtask", select_next_subtask)
learn_graph.add_node("run_react_subgraph", run_react_subgraph)
learn_graph.add_node("summarize_subtask", summarize_subtask)
learn_graph.add_node("finalize_summary", finalize_summary)
learn_graph.add_edge(START, "plan_node")
learn_graph = learn_graph.compile()
