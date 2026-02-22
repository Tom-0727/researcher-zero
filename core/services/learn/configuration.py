import os
from typing import Any

from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field



class LearnConfig(BaseModel):
    """Runtime configuration for learn graph."""

    plan_model: str = Field(
        default="glm",
        description="Model used for plan generation.",
    )
    react_think_model: str = Field(
        default="glm",
        description="Model used for ReAct think step.",
    )
    summary_model: str = Field(
        default="glm",
        description="Model used for subtask/final summaries.",
    )
    max_plan_steps: int = Field(
        default=3,
        description="Maximum number of plan items kept after parsing.",
    )
    max_react_turns_per_subtask: int = Field(
        default=6,
        description="Maximum think/act loops allowed for one subtask.",
    )
    skill_roots: list[str] = Field(
        default_factory=lambda: ["core/skills"],
        description="Skill root directories discovered by skill_meta_toolkit.",
    )
    skill_command_timeout: int = Field(
        default=120,
        description="Timeout(seconds) for skill entry command execution.",
    )

    @classmethod
    def from_runnable_config(cls, config: RunnableConfig) -> "LearnConfig":
        """Build LearnConfig from RunnableConfig configurable values."""
        configurable = config.get("configurable", {}) if config else {}
        field_names = list(cls.model_fields.keys())
        values: dict[str, Any] = {
            field_name: os.environ.get(field_name.upper(), configurable.get(field_name))
            for field_name in field_names
        }
        return cls(**{key: value for key, value in values.items() if value is not None})
