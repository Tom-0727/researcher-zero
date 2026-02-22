from typing import Literal

from langchain_core.messages import MessageLikeRepresentation
from langgraph.graph import MessagesState
from pydantic import BaseModel, Field


class PlanItem(BaseModel):
    """One canonical item parsed from <PLAN> file."""

    id: int
    title: str
    status: Literal["todo", "doing", "done", "aborted"]


class SubtaskSummary(BaseModel):
    """Compressed summary kept across subtasks."""

    subtask_id: int
    summary: str


class LearnState(MessagesState):
    """State for learn graph."""

    workspace: str
    task: str
    plan_file: str = ""
    system_prompt: str = ""
    skill_runtime_prompt: str = ""
    workspace_notes_summary: str = ""
    available_skills: list[str] = Field(default_factory=list)
    plan_items: list[PlanItem] = Field(default_factory=list)
    current_index: int = 0
    current_subtask_id: int = 0
    current_subtask: str = ""
    react_turn: int = 0
    stop_reason: str = ""
    subtask_summaries: list[SubtaskSummary] = Field(default_factory=list)
    react_messages: list[MessageLikeRepresentation] = Field(default_factory=list)
    condensed_messages: list[MessageLikeRepresentation] = Field(default_factory=list)
    final_summary: str = ""
    done: bool = False
