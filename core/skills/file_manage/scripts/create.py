from .errors import FileAlreadyExistsError
from .workspace import WorkspaceGuard


def create_file_in_workspace(
    guard: WorkspaceGuard,
    path: str,
    content: str = "",
    overwrite: bool = False,
    encoding: str = "utf-8",
) -> str:
    abs_path = guard.resolve_path(path)
    abs_path.parent.mkdir(parents=True, exist_ok=True)

    if abs_path.exists() and not overwrite:
        raise FileAlreadyExistsError(f"File already exists: {guard.rel_path(path)}")

    abs_path.write_text(content, encoding=encoding)
    return abs_path.relative_to(guard.root).as_posix()
