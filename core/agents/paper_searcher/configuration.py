import os
from typing import Any
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field


class PaperSearcherConfig(BaseModel):
    max_think_turns: int = Field(
        default=3,
        description="The maximum number of search turns to perform"
    )
    max_search_results: int = Field(
        default=5,
        description="The maximum number of search results to return"
    )
    paper_searcher_think_model: str = Field(
        default="deepseek",
        description="The model to use for generating the search queries"
    )

    @classmethod
    def from_runnable_config(cls, config: RunnableConfig) -> "PaperSearcherConfig":
        """Create a Configuration instance from a RunnableConfig."""
        configurable = config.get("configurable", {}) if config else {}
        field_names = list(cls.model_fields.keys())
        values: dict[str, Any] = {
            field_name: os.environ.get(field_name.upper(), configurable.get(field_name))
            for field_name in field_names
        }
        return cls(**{k: v for k, v in values.items() if v is not None})