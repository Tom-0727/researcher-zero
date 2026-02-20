import json
import re
import shlex
from typing import Any, Literal

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command
from pydantic import BaseModel, Field

from core.researcher_zero.learn.configuration import LearnConfig
from core.researcher_zero.learn.prompts import (
    get_react_think_prompt,
    render_plan_view,
)
from core.researcher_zero.learn.state import LearnState
from core.tools.skill_meta_toolkit import build_skill_capability

load_dotenv()
configurable_model = init_chat_model(
    configurable_fields=("model", "max_tokens", "temperature", "model_provider"),
)
EXIT_CODE_RE = re.compile(r"^exit_code:\s*(-?\d+)\s*$")
READ_OPS = {"ingest", "outline", "find", "read"}
READ_STAGE_INGESTED = "ingested"
READ_STAGE_LOCATED = "located"
READ_STAGE_READ = "read"


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
        allow_run_entry=configurable.skill_allow_run_entry,
        command_timeout=configurable.skill_command_timeout,
        allowed_entry_programs=tuple(configurable.skill_allowed_entry_programs),
    )
    tool_map = {tool_obj.name: tool_obj for tool_obj in capability.tools}
    return configurable, capability.tools, tool_map


def _normalize_tool_payload(payload: Any) -> str:
    """Normalize tool payload as text."""
    if isinstance(payload, str):
        return payload
    return str(payload)


def _extract_flag_value(tokens: list[str], flag: str) -> str:
    """Extract one '--flag value' argument from tokens."""
    for idx, token in enumerate(tokens):
        if token != flag:
            continue
        if idx + 1 >= len(tokens) or tokens[idx + 1].startswith("--"):
            raise ValueError(f"Missing value for {flag}.")
        return tokens[idx + 1].strip()
    return ""


def _parse_chunk_ids(raw: str) -> list[int]:
    """Parse and validate comma-separated chunk ids."""
    parts = [part.strip() for part in raw.split(",")]
    ids = [part for part in parts if part]
    if not ids:
        raise ValueError("read op requires non-empty --chunk-ids.")
    seen: set[int] = set()
    parsed: list[int] = []
    for item in ids:
        if not item.isdigit() or item == "0":
            raise ValueError(f"Invalid chunk id: {item!r}")
        value = int(item)
        if value in seen:
            raise ValueError(f"Duplicate chunk id: {value}")
        seen.add(value)
        parsed.append(value)
    return parsed


def _extract_run_skill_entry_call(tool_name: str, tool_args: dict[str, Any]) -> tuple[str, str] | None:
    """Extract run_skill_entry(skill_name, args) payload."""
    if tool_name != "run_skill_entry":
        return None
    skill_name = str(tool_args.get("skill_name", "")).strip()
    if not skill_name:
        raise ValueError("run_skill_entry.skill_name cannot be empty.")
    args_text = str(tool_args.get("args", "")).strip()
    return skill_name, args_text


def _parse_read_entry_args(args_text: str) -> dict[str, str]:
    """Parse run_skill_entry args for read skill and validate required flags."""
    tokens = shlex.split(args_text)
    if not tokens:
        raise ValueError("read skill args cannot be empty.")
    workspace = _extract_flag_value(tokens, "--workspace")
    if not workspace:
        raise ValueError("read skill args must include --workspace.")

    op = ""
    for token in tokens:
        if token in READ_OPS:
            op = token
            break
    if not op:
        raise ValueError(
            "read skill args must include one operation: ingest|outline|find|read."
        )

    parsed = {
        "workspace": workspace,
        "op": op,
        "doc_id": "",
        "chunk_ids": "",
    }
    if op == "ingest":
        source = _extract_flag_value(tokens, "--source")
        if not source:
            raise ValueError("read ingest requires --source.")
        return parsed

    doc_id = _extract_flag_value(tokens, "--doc-id")
    if not doc_id:
        raise ValueError(f"read {op} requires --doc-id.")
    parsed["doc_id"] = doc_id

    if op == "find":
        query = _extract_flag_value(tokens, "--query")
        if not query:
            raise ValueError("read find requires --query.")
    if op == "read":
        chunk_ids = _extract_flag_value(tokens, "--chunk-ids")
        if not chunk_ids:
            raise ValueError("read read requires --chunk-ids.")
        _parse_chunk_ids(chunk_ids)
        parsed["chunk_ids"] = chunk_ids
    return parsed


def _validate_read_sequence(state: LearnState, read_meta: dict[str, str]) -> None:
    """Enforce ingest -> outline/find -> read sequence in current subtask."""
    op = read_meta["op"]
    if op == "ingest":
        return

    doc_id = read_meta["doc_id"].strip()
    stage = str(state.get("read_doc_stage", {}).get(doc_id, "")).strip()
    if not stage:
        raise ValueError(
            f"read doc_id={doc_id!r} has no ingest record in current subtask. "
            "Call ingest first."
        )
    if op in {"outline", "find"}:
        return
    if stage not in {READ_STAGE_LOCATED, READ_STAGE_READ}:
        raise ValueError(
            f"read doc_id={doc_id!r} must run outline/find before read(chunk-ids)."
        )


def _precheck_run_skill_entry(
    state: LearnState,
    tool_name: str,
    tool_args: dict[str, Any],
) -> dict[str, str] | None:
    """Validate run_skill_entry payload before invocation."""
    entry = _extract_run_skill_entry_call(tool_name, tool_args)
    if not entry:
        return None
    skill_name, args_text = entry
    if skill_name != "read":
        return {"skill_name": skill_name, "args": args_text}

    read_meta = _parse_read_entry_args(args_text)
    _validate_read_sequence(state, read_meta)
    return {
        "skill_name": "read",
        "args": args_text,
        **read_meta,
    }


def _extract_entry_stdout(payload: str) -> str:
    """Extract stdout part from run_skill_entry payload."""
    parts = payload.split("\n\n", maxsplit=1)
    if len(parts) < 2:
        return ""
    return parts[1].strip()


def _parse_read_output_json(payload: str) -> dict[str, Any]:
    """Parse JSON payload emitted by read skill."""
    stdout = _extract_entry_stdout(payload)
    if not stdout:
        raise ValueError("read skill returned empty stdout payload.")
    try:
        parsed = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise ValueError("read skill stdout is not valid JSON.") from exc
    if not isinstance(parsed, dict):
        raise ValueError("read skill stdout payload must be a JSON object.")
    return parsed


def _apply_read_stage_update(
    state: LearnState,
    entry_meta: dict[str, str] | None,
    payload: str,
) -> dict[str, str]:
    """Update read_doc_stage map after successful run_skill_entry."""
    next_stage = dict(state.get("read_doc_stage", {}))
    if not entry_meta or entry_meta.get("skill_name") != "read":
        return next_stage

    op = entry_meta["op"]
    if op == "ingest":
        parsed = _parse_read_output_json(payload)
        data = parsed.get("data", {})
        doc_id = str(data.get("doc_id", "")).strip() if isinstance(data, dict) else ""
        if not doc_id:
            raise ValueError("read ingest output missing data.doc_id.")
        next_stage[doc_id] = READ_STAGE_INGESTED
        return next_stage

    doc_id = entry_meta["doc_id"].strip()
    if op in {"outline", "find"}:
        next_stage[doc_id] = READ_STAGE_LOCATED
    elif op == "read":
        next_stage[doc_id] = READ_STAGE_READ
    return next_stage


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
    entry_meta = _precheck_run_skill_entry(state, tool_name, tool_args)
    payload = _normalize_tool_payload(tool.invoke(tool_args))
    _raise_on_failed_run_skill_entry(tool_name, payload)
    read_doc_stage = _apply_read_stage_update(state, entry_meta, payload)

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
            "read_doc_stage": read_doc_stage,
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
