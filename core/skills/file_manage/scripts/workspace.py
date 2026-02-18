from pathlib import Path

from .errors import WorkspaceViolationError


class WorkspaceGuard:
    """Resolves and validates all file paths inside a fixed workspace root."""

    def __init__(self, workspace_root: str | Path):
        self.root = Path(workspace_root).resolve()
        if not self.root.exists():
            self.root.mkdir(parents=True, exist_ok=True)

    def resolve_path(self, path: str | Path) -> Path:
        path_obj = Path(path)
        if path_obj.is_absolute():
            resolved = path_obj.resolve(strict=False)
        else:
            resolved = (self.root / path_obj).resolve(strict=False)

        if not resolved.is_relative_to(self.root):
            raise WorkspaceViolationError(
                f"Path '{path}' is outside workspace '{self.root}'."
            )
        return resolved

    def rel_path(self, path: str | Path) -> str:
        resolved = self.resolve_path(path)
        return resolved.relative_to(self.root).as_posix()
