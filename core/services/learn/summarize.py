import json
from typing import Any

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from core.services.learn.configuration import LearnConfig
from core.services.learn.prompts import (
    get_final_summary_prompt,
    get_subtask_summary_prompt,
    render_plan_view,
    render_subtask_summaries,
)
from core.services.learn.state import LearnState, SubtaskSummary

load_dotenv()
configurable_model = init_chat_model(
    configurable_fields=("model", "max_tokens", "temperature", "model_provider"),
)


def _extract_message_text(message: Any) -> str:
    """Extract text body from message-like objects."""
    content = getattr(message, "content", message)
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        rows: list[str] = []
        for item in content:
            if isinstance(item, str):
                text = item.strip()
                if text:
                    rows.append(text)
                continue
            if isinstance(item, dict):
                text = str(item.get("text", "")).strip()
                if text:
                    rows.append(text)
        return "\n".join(rows).strip()
    return str(content).strip()


def _render_react_trace(react_messages: list[Any]) -> str:
    """Render current subtask trace for summary model input."""
    if not react_messages:
        raise ValueError("react_messages is empty when summarizing subtask.")

    lines: list[str] = []
    for message in react_messages:
        role = type(message).__name__
        body = _extract_message_text(message)
        if body:
            lines.append(f"[{role}] {body}")
        tool_calls = getattr(message, "tool_calls", [])
        for tool_call in tool_calls:
            name = tool_call.get("name", "")
            args = json.dumps(tool_call.get("args", {}) or {}, ensure_ascii=False)
            lines.append(f"[tool_call] {name} {args}")
    if not lines:
        raise ValueError("react_messages has no readable content for summary.")
    return "\n".join(lines)


def _extract_model_text(response: Any) -> str:
    """Require non-empty model text output."""
    text = _extract_message_text(response).strip()
    if not text:
        raise ValueError("Summary model returned empty content.")
    return text


async def run_subtask_summary(state: LearnState, config: RunnableConfig) -> dict[str, Any]:
    """Summarize current subtask trace and compact cross-subtask memory."""
    current_subtask_id = int(state.get("current_subtask_id", 0))
    current_subtask = str(state.get("current_subtask", "")).strip()
    if current_subtask_id <= 0:
        raise ValueError("current_subtask_id must be positive before summarization.")
    if not current_subtask:
        raise ValueError("current_subtask cannot be empty before summarization.")

    configurable = LearnConfig.from_runnable_config(config)
    model_config = {
        "model": configurable.summary_model,
        "model_provider": "openai",
        "max_tokens": 8000,
        "temperature": 0.1,
        "timeout": configurable.skill_command_timeout,
    }
    trace = _render_react_trace(state.get("react_messages", []))
    prompt = get_subtask_summary_prompt(
        current_subtask_id=current_subtask_id,
        current_subtask=current_subtask,
    )
    response = await configurable_model.with_config(model_config).ainvoke(
        [
            SystemMessage(content=state["system_prompt"]),
            HumanMessage(content=f"{prompt}\n\nSubtask trace:\n{trace}"),
        ]
    )
    summary_text = _extract_model_text(response)
    summary_item = SubtaskSummary(
        subtask_id=current_subtask_id,
        summary=summary_text,
    )
    summary_line = f"[{current_subtask_id}] {summary_text}"
    return {
        "messages": [response],
        "subtask_summaries": [*state.get("subtask_summaries", []), summary_item],
        "condensed_messages": [
            *state.get("condensed_messages", []),
            HumanMessage(content=summary_line),
        ],
        "react_messages": [],
        "react_turn": 0,
        "stop_reason": "",
        "current_subtask": "",
        "current_subtask_id": 0,
    }


async def run_finalize_summary(state: LearnState, config: RunnableConfig) -> dict[str, Any]:
    """Generate final report after all subtasks finish."""
    configurable = LearnConfig.from_runnable_config(config)
    model_config = {
        "model": configurable.summary_model,
        "model_provider": "openai",
        "max_tokens": 8000,
        "temperature": 0.1,
        "timeout": configurable.skill_command_timeout,
    }
    prompt = get_final_summary_prompt(
        task=state["task"],
        plan_view=render_plan_view(state.get("plan_items", [])),
        summaries_view=render_subtask_summaries(state.get("subtask_summaries", [])),
    )
    response = await configurable_model.with_config(model_config).ainvoke(
        [
            SystemMessage(content=state["system_prompt"]),
            HumanMessage(content=prompt),
        ]
    )
    final_summary = _extract_model_text(response)
    return {
        "messages": [response],
        "final_summary": final_summary,
        "done": True,
    }
