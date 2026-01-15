import operator
from typing import Annotated, List, Optional

from langchain_core.messages import MessageLikeRepresentation
from langgraph.graph import MessagesState
from pydantic import BaseModel, Field


class ConductSearch(BaseModel):
    """Call this tool to conduct a single Semantic Scholar search."""

    query: str = Field(
        description="Keyword-based Semantic Scholar query"
    )


class SearchComplete(BaseModel):
    """Call this tool to indicate that the paper search is complete."""


class PaperResult(BaseModel):
    id: Optional[str]
    title: str
    year: Optional[int]
    citations: int
    abstract: str
    link: Optional[str]


class PaperSearcherState(MessagesState):
    """State for iterative paper search."""

    paper_search_task: str
    think_turns: int = Field(default=0)
    search_queries: List[str] = Field(default_factory=list)
    search_results: List[PaperResult] = Field(default_factory=list)
    searcher_messages: Annotated[
        list[MessageLikeRepresentation],
        operator.add
    ] = Field(default_factory=list)
