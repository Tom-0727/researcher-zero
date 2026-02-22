import re
from typing import Any, Literal

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command
from pydantic import BaseModel, Field

from core.services.learn.configuration import LearnConfig
from core.services.learn.prompts import (
    get_react_skills_instruction,
    get_react_think_prompt,
    render_plan_view,
)
from core.services.learn.state import LearnState
from core.tools.skill_meta_toolkit import build_skill_capability

load_dotenv()
configurable_model = init_chat_model(
    configurable_fields=("model", "max_tokens", "temperature", "model_provider"),
)
EXIT_CODE_RE = re.compile(r"^exit_code:\s*(-?\d+)\s*$")


class FinishSubtask(BaseModel):
    """Call this tool when current subtask has enough evidence."""

    reason: str = Field(
        default="",
        description="Optional reason for stopping the current subtask.",
    )


def _extract_message_text(message: Any) -> str:
    """Extract text content from message-like objects."""
    content = getattr(message, "content", message)
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        fragments: list[str] = []
        for item in content:
            if isinstance(item, str):
                text = item.strip()
                if text:
                    fragments.append(text)
                continue
            if isinstance(item, dict):
                text = str(item.get("text", "")).strip()
                if text:
                    fragments.append(text)
        return "\n".join(fragments).strip()
    return str(content).strip()


def _render_condensed_history(condensed_messages: list[Any]) -> str:
    """Render cross-subtask compressed history into compact text."""
    rows: list[str] = []
    for message in condensed_messages:
        text = _extract_message_text(message)
        if text:
            rows.append(text)
    return "\n\n".join(rows) if rows else "(none)"


def _build_react_input_messages(
    *,
    state: LearnState,
    react_turn: int,
    max_react_turns: int,
) -> list[Any]:
    """Build ordered message list for one ReAct think turn."""
    messages: list[Any] = [
        SystemMessage(content=state["system_prompt"]),
        HumanMessage(content=f"Current plan:\n{render_plan_view(state.get('plan_items', []))}"),
        HumanMessage(
            content=(
                "Previous subtask summaries:\n"
                f"{_render_condensed_history(state.get('condensed_messages', []))}"
            )
        ),
        HumanMessage(
            content=str(state.get("skill_runtime_prompt", ""))
        ),
        HumanMessage(
            content=get_react_think_prompt(
                current_subtask_id=state.get("current_subtask_id", 0),
                current_subtask=state.get("current_subtask", ""),
                react_turn=react_turn,
                max_react_turns=max_react_turns,
            )
        ),
    ]
    trace = state.get("react_messages", [])
    if trace:
        messages.extend(trace)
    return messages


def _build_skill_tools(config: RunnableConfig) -> tuple[LearnConfig, list[Any], dict[str, Any]]:
    """Build skill meta toolkit tools for one react step."""
    configurable = LearnConfig.from_runnable_config(config)
    capability = build_skill_capability(
        roots=configurable.skill_roots,
        allow_run_entry=True,
        command_timeout=configurable.skill_command_timeout,
        only_tools=["load_skill", "run_skill_entry"],
    )
    capability.prompt = """## Skills usage instructions

When you need a skill:
1. Call **load_skill(skill_name)** first, the response describes what the skill does and how to use it.
2. Call **run_skill_entry(skill_name, entry_args)**. **entry_args** is a single string: the CLI argument list you would pass to that skill's entry (same as on the command line). Use double quotes for values that contain spaces; the string is parsed with shell rules (e.g. `--provider semantic_scholar --query "your query"`). Copy the format from the examples in load_skill's response.


"""
    tool_map = {tool_obj.name: tool_obj for tool_obj in capability.tools}
    return configurable, capability.tools, tool_map


def _normalize_tool_payload(payload: Any) -> str:
    """Normalize tool payload as text."""
    if isinstance(payload, str):
        return payload
    return str(payload)


def _raise_on_failed_run_skill_entry(tool_name: str, payload: str) -> None:
    """Raise explicit error when run_skill_entry exits non-zero."""
    if tool_name != "run_skill_entry":
        return
    first_line = payload.splitlines()[0].strip() if payload.splitlines() else ""
    matched = EXIT_CODE_RE.fullmatch(first_line)
    if not matched:
        raise RuntimeError(f"run_skill_entry returned unexpected payload.\n{payload}")
    if int(matched.group(1)) != 0:
        raise RuntimeError(f"run_skill_entry failed.\n{payload}")


def _pick_single_tool_call(response: Any) -> dict[str, Any]:
    """Require exactly one tool call for each think turn."""
    tool_calls = getattr(response, "tool_calls", [])
    if not tool_calls:
        raise ValueError("react_think expects exactly one tool call, got none.")
    if len(tool_calls) != 1:
        raise ValueError("react_think expects exactly one tool call.")
    return tool_calls[0]


async def react_think(
    state: LearnState,
    config: RunnableConfig,
) -> Command[Literal["react_act"]]:
    """Decide the next single action for the current subtask."""
    configurable, skill_tools, _tool_map = _build_skill_tools(config)
    actions = [*skill_tools, FinishSubtask]
    model_config = {
        "model": configurable.react_think_model,
        "model_provider": "openai",
        "max_tokens": 8000,
        "temperature": 0.1,
        "timeout": configurable.skill_command_timeout,
    }
    think_model = (
        configurable_model
        .bind_tools(actions, tool_choice="required")
        .with_config(model_config)
    )

    react_turn = state.get("react_turn", 0) + 1
    messages = _build_react_input_messages(
        state=state,
        react_turn=react_turn,
        max_react_turns=configurable.max_react_turns_per_subtask,
    )

    breakpoint()
    response = await think_model.ainvoke(messages)
    _pick_single_tool_call(response)
    return Command(
        goto="react_act",
        update={
            "react_messages": [*state.get("react_messages", []), response],
            "react_turn": react_turn,
        },
    )


async def react_act(
    state: LearnState,
    config: RunnableConfig,
) -> Command[Literal["react_should_stop"]]:
    """Execute one selected action and append tool output to trace."""
    _, _skill_tools, tool_map = _build_skill_tools(config)
    trace = state.get("react_messages", [])
    if not trace:
        raise ValueError("react_messages is empty before react_act.")
    latest = trace[-1]
    tool_call = _pick_single_tool_call(latest)
    tool_name = tool_call.get("name", "")
    tool_args = tool_call.get("args", {}) or {}

    if tool_name == FinishSubtask.__name__:
        reason = str(tool_args.get("reason", "")).strip() or "model_finish"
        return Command(
            goto="react_should_stop",
            update={"stop_reason": reason},
        )

    tool = tool_map.get(tool_name)
    if not tool:
        raise ValueError(f"Unsupported tool call in react_act: {tool_name!r}")
    payload = _normalize_tool_payload(tool.invoke(tool_args))
    _raise_on_failed_run_skill_entry(tool_name, payload)

    tool_call_id = tool_call.get("id")
    if not tool_call_id:
        raise ValueError("Missing tool_call id in react_act.")
    return Command(
        goto="react_should_stop",
        update={
            "react_messages": [
                *state.get("react_messages", []),
                ToolMessage(
                    content=payload,
                    tool_call_id=tool_call_id,
                ),
            ],
            "stop_reason": "",
        },
    )


async def react_should_stop(
    state: LearnState,
    config: RunnableConfig,
) -> Command[Literal["react_think", "__end__"]]:
    """Stop when model finished or max turns reached."""
    configurable = LearnConfig.from_runnable_config(config)
    reason = state.get("stop_reason", "").strip()
    if reason:
        return Command(goto=END)
    if state.get("react_turn", 0) >= configurable.max_react_turns_per_subtask:
        return Command(
            goto=END,
            update={"stop_reason": "max_react_turns"},
        )
    return Command(goto="react_think")


react_subgraph = StateGraph(LearnState)
react_subgraph.add_node("react_think", react_think)
react_subgraph.add_node("react_act", react_act)
react_subgraph.add_node("react_should_stop", react_should_stop)
react_subgraph.add_edge(START, "react_think")
react_subgraph = react_subgraph.compile()
