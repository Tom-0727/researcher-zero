import json
from pathlib import Path
from typing import Any

from langchain_core.tools import tool

from core.skills.plan.scripts.plan_tool import mutate_plan_file


def _resolve_plan_file(plan_file: str) -> str:
    """Normalize plan file path to absolute path."""
    return str(Path(plan_file).expanduser().resolve())


def _validate_upsert_todos_payload(items_json: str) -> None:
    """Validate strict append-only todo payload."""
    payload = json.loads(items_json)
    if not isinstance(payload, list) or not payload:
        raise ValueError("items_json must be a non-empty JSON array.")
    for index, item in enumerate(payload, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"items_json[{index}] must be an object.")
        if "id" in item:
            raise ValueError("plan_upsert_todos does not allow id in payload.")
        if item.get("status") != "todo":
            raise ValueError("plan_upsert_todos requires status='todo'.")
        title = item.get("title")
        if not isinstance(title, str) or not title.strip():
            raise ValueError(f"items_json[{index}].title must be a non-empty string.")


def _validate_remove_ids(ids: str) -> None:
    """Validate comma-separated positive ids payload."""
    parts = [part.strip() for part in ids.split(",")]
    values = [part for part in parts if part]
    if not values:
        raise ValueError("ids must contain at least one id.")
    seen: set[int] = set()
    for raw in values:
        if not raw.isdigit() or raw == "0":
            raise ValueError(f"Invalid id in ids: {raw!r}")
        parsed = int(raw)
        if parsed in seen:
            raise ValueError(f"Duplicate id in ids: {parsed}")
        seen.add(parsed)


def _upsert_todos(plan_file: str, items_json: str) -> str:
    """Call plan skill upsert operation with strict todo-only payload."""
    _validate_upsert_todos_payload(items_json)
    return mutate_plan_file(
        plan_path=_resolve_plan_file(plan_file),
        op="upsert",
        items_json=items_json,
        ids_csv=None,
    )


def _remove_ids(plan_file: str, ids: str) -> str:
    """Call plan skill remove operation."""
    _validate_remove_ids(ids)
    return mutate_plan_file(
        plan_path=_resolve_plan_file(plan_file),
        op="remove",
        items_json=None,
        ids_csv=ids,
    )


@tool
def plan_upsert_todos(plan_file: str, items_json: str) -> str:
    """
    Append todo steps into a canonical <PLAN> file.

    Args:
        plan_file: Absolute/relative path to plan markdown file.
        items_json: JSON array, each item must be {"status":"todo","title":"..."}.
    """
    return _upsert_todos(plan_file=plan_file, items_json=items_json)


@tool
def plan_remove_ids(plan_file: str, ids: str) -> str:
    """
    Remove plan rows by ids from a canonical <PLAN> file.

    Args:
        plan_file: Absolute/relative path to plan markdown file.
        ids: Comma-separated ids, e.g. "2,4".
    """
    return _remove_ids(plan_file=plan_file, ids=ids)


def build_plan_tools(plan_file: str | None = None) -> list[Any]:
    """Build plan tools; optionally bind one fixed plan_file path."""
    if not plan_file:
        return [plan_upsert_todos, plan_remove_ids]

    resolved_plan_file = _resolve_plan_file(plan_file)

    @tool
    def plan_upsert_todos(items_json: str) -> str:
        """
        Append todo steps into the bound <PLAN> file.

        Args:
            items_json: JSON array, each item must be {"status":"todo","title":"..."}.
        """
        return _upsert_todos(plan_file=resolved_plan_file, items_json=items_json)

    @tool
    def plan_remove_ids(ids: str) -> str:
        """
        Remove plan rows by ids from the bound <PLAN> file.

        Args:
            ids: Comma-separated ids, e.g. "2,4".
        """
        return _remove_ids(plan_file=resolved_plan_file, ids=ids)

    return [plan_upsert_todos, plan_remove_ids]
