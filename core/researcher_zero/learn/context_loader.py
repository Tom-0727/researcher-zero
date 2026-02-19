from pathlib import Path
from typing import Final


REQUIRED_CONTEXT_FILES: Final[dict[str, str]] = {
    "basic_info": "Basic_Context/basic_info.md",
    "taxonomy": "Basic_Context/taxonomy.md",
    "network": "Cognition/network.md",
    "main_challenge": "Cognition/main_challenge.md",
}


def _resolve_workspace(workspace: str | Path) -> Path:
    """Resolve and validate workspace path."""
    if not str(workspace).strip():
        raise ValueError("workspace cannot be empty")

    workspace_path = Path(workspace).expanduser().resolve()
    if not workspace_path.exists():
        raise FileNotFoundError(f"workspace does not exist: {workspace_path}")
    if not workspace_path.is_dir():
        raise NotADirectoryError(f"workspace is not a directory: {workspace_path}")
    return workspace_path


def load_plan_context(workspace: str | Path) -> dict[str, str]:
    """Load required markdown context files for the plan stage."""
    workspace_path = _resolve_workspace(workspace)
    context: dict[str, str] = {}

    for key, relative_path in REQUIRED_CONTEXT_FILES.items():
        # Plan 阶段只接受四个固定文件，缺任意一个直接报错。
        target = workspace_path / relative_path
        if not target.exists():
            raise FileNotFoundError(f"missing required context file: {target}")
        if not target.is_file():
            raise IsADirectoryError(f"required context path is not a file: {target}")
        context[key] = target.read_text(encoding="utf-8")

    return context
