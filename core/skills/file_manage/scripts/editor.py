from dataclasses import dataclass
from pathlib import Path

from .edit_blocks import EditBlock, apply_search_replace, parse_edit_blocks
from .errors import EditMatchError
from .workspace import WorkspaceGuard


@dataclass(frozen=True)
class EditOutcome:
    path: str
    changed: bool


def edit_file_in_workspace(
    guard: WorkspaceGuard,
    path: str,
    search: str,
    replace: str,
    encoding: str = "utf-8",
) -> EditOutcome:
    abs_path = guard.resolve_path(path)
    abs_path.parent.mkdir(parents=True, exist_ok=True)

    if not abs_path.exists():
        if search.strip():
            raise EditMatchError(f"Target file does not exist: {guard.rel_path(path)}")
        abs_path.write_text("", encoding=encoding)

    original = abs_path.read_text(encoding=encoding)
    updated = apply_search_replace(original, search, replace, path=path)
    changed = updated != original
    if changed:
        abs_path.write_text(updated, encoding=encoding)

    return EditOutcome(path=abs_path.relative_to(guard.root).as_posix(), changed=changed)


def apply_edit_blocks_in_workspace(
    guard: WorkspaceGuard,
    instruction_text: str,
    valid_files: list[str] | None = None,
    encoding: str = "utf-8",
) -> list[EditOutcome]:
    valid_files = valid_files or []
    blocks: list[EditBlock] = parse_edit_blocks(instruction_text, valid_files=valid_files)
    outcomes: list[EditOutcome] = []
    for block in blocks:
        outcome = edit_file_in_workspace(
            guard=guard,
            path=block.path,
            search=block.search,
            replace=block.replace,
            encoding=encoding,
        )
        outcomes.append(outcome)
    return outcomes
