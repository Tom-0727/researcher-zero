import os
from typing import Any

from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field


def _parse_bool(raw: Any) -> bool:
    """Parse bool from env/configurable values."""
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, str):
        normalized = raw.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    raise ValueError(f"Invalid boolean value: {raw!r}")


def _parse_csv_or_list(raw: Any) -> list[str]:
    """Parse comma-separated string or list into string list."""
    if isinstance(raw, list):
        return [str(item).strip() for item in raw if str(item).strip()]
    if isinstance(raw, str):
        return [part.strip() for part in raw.split(",") if part.strip()]
    raise ValueError(f"Invalid list value: {raw!r}")


class LearnConfig(BaseModel):
    """Runtime configuration for learn graph."""

    plan_model: str = Field(
        default="deepseek",
        description="Model used for plan generation.",
    )
    react_think_model: str = Field(
        default="deepseek",
        description="Model used for ReAct think step.",
    )
    summary_model: str = Field(
        default="deepseek",
        description="Model used for subtask/final summaries.",
    )
    max_plan_steps: int = Field(
        default=8,
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
    skill_allow_run_entry: bool = Field(
        default=True,
        description="Whether run_skill_entry is enabled for skill runtime.",
    )
    skill_command_timeout: int = Field(
        default=60,
        description="Timeout(seconds) for skill entry command execution.",
    )
    skill_allowed_entry_programs: list[str] = Field(
        default_factory=lambda: ["python", "python3", "bash", "sh"],
        description="Allowed entry programs for run_skill_entry.",
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
        filtered = {key: value for key, value in values.items() if value is not None}
        if "skill_allow_run_entry" in filtered:
            filtered["skill_allow_run_entry"] = _parse_bool(filtered["skill_allow_run_entry"])
        if "skill_roots" in filtered:
            filtered["skill_roots"] = _parse_csv_or_list(filtered["skill_roots"])
        if "skill_allowed_entry_programs" in filtered:
            filtered["skill_allowed_entry_programs"] = _parse_csv_or_list(
                filtered["skill_allowed_entry_programs"]
            )
        return cls(**filtered)
