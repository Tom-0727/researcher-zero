import operator
from typing import Annotated, Literal

from langchain_core.messages import MessageLikeRepresentation
from langgraph.graph import MessagesState
from pydantic import BaseModel, Field


class PlanItem(BaseModel):
    """A decomposed learn subtask."""

    id: str
    title: str
    status: Literal["todo", "done"] = "todo"


class SubtaskSummary(BaseModel):
    """Condensed summary for one completed subtask."""

    subtask_id: str
    summary: str


class LearnState(MessagesState):
    """State for learn graph with plan-execute-react flow."""

    workspace: str
    task: str
    system_prompt: str = ""
    plan_items: list[PlanItem] = Field(default_factory=list)
    current_index: int = 0
    current_subtask: str = ""
    subtask_summaries: list[SubtaskSummary] = Field(default_factory=list)
    react_messages: Annotated[
        list[MessageLikeRepresentation],
        operator.add,
    ] = Field(default_factory=list)
    condensed_messages: Annotated[
        list[MessageLikeRepresentation],
        operator.add,
    ] = Field(default_factory=list)
    final_summary: str = ""
    done: bool = False
