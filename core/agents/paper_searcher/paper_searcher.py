import asyncio
from typing import List, Literal

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from core.agents.paper_searcher.configuration import PaperSearcherConfig
from core.agents.paper_searcher.prompts import (
    get_paper_searcher_think_prompt,
    get_system_prompt,
)
from core.agents.paper_searcher.state import (
    PaperResult,
    PaperSearcherState,
    SearchComplete,
)
from core.tools.search.semantic_scholar_search import search_semantic_scholar
from core.utils.logs import logger

load_dotenv()
configurable_model = init_chat_model(
    configurable_fields=("model", "max_tokens", "temperature", "model_provider"),
)
logger.info("Configurable model initialized.")


async def paper_searcher_think(
    state: PaperSearcherState,
    config: RunnableConfig,
) -> Command[Literal["paper_searcher_act"]]:
    """Plan the next search query or decide to finish."""
    configurable = PaperSearcherConfig.from_runnable_config(config)
    model_config = {
        "model": configurable.paper_searcher_think_model,
        "model_provider": "openai",
        "max_tokens": 8000,
        "temperature": 0.1,
        "timeout": 120,
    }

    actions = [search_semantic_scholar, SearchComplete]
    think_model = (
        configurable_model
        .bind_tools(actions, tool_choice="required")
        .with_config(model_config)
    )

    history_queries = state.get("search_queries", [])
    history_results = state.get("search_results", [])
    think_prompt = get_paper_searcher_think_prompt(
        state.get("paper_search_task", ""),
        history_queries,
        history_results,
    )

    messages = [
        SystemMessage(content=get_system_prompt()),
        HumanMessage(content=think_prompt),
    ]
    response = await think_model.ainvoke(messages)

    return Command(
        goto="paper_searcher_act",
        update={
            "searcher_messages": [response],
            "think_turns": state.get("think_turns", 0) + 1,
        },
    )


async def paper_searcher_act(
    state: PaperSearcherState,
    config: RunnableConfig,
) -> Command[Literal["paper_searcher_think", "__end__"]]:
    """Execute the planned search and update state."""
    configurable = PaperSearcherConfig.from_runnable_config(config)
    searcher_messages = state.get("searcher_messages", [])
    most_recent_message = searcher_messages[-1]

    if not most_recent_message.tool_calls:
        raise ValueError("Expected tool calls, but none were returned.")

    if any(
        tool_call["name"] == SearchComplete.__name__
        for tool_call in most_recent_message.tool_calls
    ):
        return Command(goto=END)

    search_tool_name = search_semantic_scholar.name
    search_calls = [
        tool_call for tool_call in most_recent_message.tool_calls
        if tool_call["name"] == search_tool_name
    ]
    if not search_calls:
        raise ValueError(f"Expected {search_tool_name} tool call.")

    tool_call = search_calls[0]
    tool_args = tool_call.get("args", {}) or {}
    query = (tool_args.get("query") or "").strip()
    if not query:
        raise ValueError(f"{search_tool_name}.query cannot be empty.")

    logger.info(f"Running Semantic Scholar search for: {query}")
    raw_results = await search_semantic_scholar.ainvoke(
        {"query": query, "limit": configurable.max_search_results}
    )

    normalized_results: List[PaperResult] = []
    for item in raw_results:
        if "error" in item:
            raise RuntimeError(item["error"])
        normalized_results.append(PaperResult(**item))

    updated_results = state.get("search_results", []) + normalized_results
    updated_queries = state.get("search_queries", []) + [query]
    tool_messages = [
        ToolMessage(
            content=str(raw_results),
            tool_call_id=tool_call["id"],
        )
    ]

    next_node: Literal["paper_searcher_think", "__end__"] = "paper_searcher_think"
    # Enforce max search turns after each executed query.
    if state.get("think_turns", 0) >= configurable.max_think_turns:
        next_node = END

    return Command(
        goto=next_node,
        update={
            "search_results": updated_results,
            "search_queries": updated_queries,
            "searcher_messages": tool_messages,
        },
    )


paper_searcher_graph = StateGraph(PaperSearcherState)
paper_searcher_graph.add_node("paper_searcher_think", paper_searcher_think)
paper_searcher_graph.add_node("paper_searcher_act", paper_searcher_act)
paper_searcher_graph.add_edge(START, "paper_searcher_think")
paper_searcher_graph = paper_searcher_graph.compile()


async def main():
    """Run a quick local smoke test for the paper searcher."""
    sample_task = "Recent evaluation metrics for retrieval-augmented generation"
    state = PaperSearcherState(
        messages=[HumanMessage(content=sample_task)],
        paper_search_task=sample_task,
        think_turns=0,
        search_queries=[],
        search_results=[],
        searcher_messages=[],
    )
    result = await paper_searcher_graph.ainvoke(state)
    logger.info(str(result))
    breakpoint()


if __name__ == "__main__":
    asyncio.run(main())
